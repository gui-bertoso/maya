import json
import queue
import threading
import math
import numpy as np
from helpers.config import get_env
from helpers.diagnostics import report_error

try:
    import vosk
    _VOSK_IMPORT_ERROR = None
except (ImportError, OSError, FileNotFoundError) as error:
    vosk = None
    _VOSK_IMPORT_ERROR = error

try:
    import sounddevice as sd
    _SOUNDDEVICE_IMPORT_ERROR = None
except (ImportError, OSError) as error:
    sd = None
    _SOUNDDEVICE_IMPORT_ERROR = error


class Voice:
    def __init__(self, model_path="models/vosk-model-small-en-us-0.15", sample_rate=16000, block_size=2000,
                 noise_suppression=True, noise_gate=180, noise_multiplier=2.2, speech_hangover=4,
                 fast_endpoint=True, endpoint_silence_ms=375):
        self.model_path = model_path
        self.sample_rate = sample_rate
        self.block_size = max(1600, int(block_size))
        self.noise_suppression = bool(noise_suppression)
        self.noise_gate = max(20.0, float(noise_gate))
        self.noise_multiplier = max(1.1, float(noise_multiplier))
        self.speech_hangover = max(0, int(speech_hangover))
        self.fast_endpoint = bool(fast_endpoint)
        self.endpoint_silence_ms = max(200, int(endpoint_silence_ms))
        block_duration_ms = (self.block_size / self.sample_rate) * 1000.0
        self.endpoint_silence_blocks = max(2, int(math.ceil(self.endpoint_silence_ms / block_duration_ms)))
        self.noise_floor = 60.0
        self._speech_blocks_remaining = 0
        self.last_rms = 0.0
        self.last_block_has_speech = False

        self.thread = None
        self._stop_requested = threading.Event()
        # Bound the backlog so an overloaded recognizer never answers old audio.
        self.audio_queue = queue.Queue(maxsize=16)

        self.model = None
        self.recognizer = None

        self.is_loaded = False
        self.is_listening = False
        self.status = "idle"
        self.last_error = None

        self.DEBUG_MODE = get_env("DEBUG_MODE", "false").lower() == "true"
        self.UI_MODE = get_env("UI_MODE", "maya")
        self.LANGUAGE = get_env("LANGUAGE", "en")

    def _set_audio_backend_error(self, reason=None):
        base_reason = reason or _SOUNDDEVICE_IMPORT_ERROR
        self.last_error = str(base_reason) if base_reason else "sounddevice is unavailable"
        report_error("microphone_dependency", base_reason, operation="voice.audio.dependency")
        return False

    def _set_vosk_backend_error(self, reason=None):
        base_reason = reason or _VOSK_IMPORT_ERROR
        self.last_error = str(base_reason) if base_reason else "vosk is unavailable"
        report_error("microphone_dependency", base_reason, operation="voice.vosk.dependency")
        return False

    def has_input_device(self):
        if sd is None:
            return self._set_audio_backend_error()

        try:
            devices = sd.query_devices()
        except Exception as error:
            self.last_error = str(error)
            report_error("microphone_device", error, operation="voice.device.query")
            return False

        for device in devices:
            if device.get("max_input_channels", 0) > 0:
                return True

        return False

    def set_status(self, status, on_status_change=None):
        self.status = status
        if on_status_change:
            on_status_change(status)

    def load_voice(self, on_status_change=None):
        if self.is_loaded:
            return

        self.set_status("loading", on_status_change)

        try:
            if vosk is None:
                self._set_vosk_backend_error()
                self.set_status("unavailable", on_status_change)
                return

            if self.DEBUG_MODE:
                print("loading vosk...")
            self.model = vosk.Model(self.model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)
            self.is_loaded = True
            if self.DEBUG_MODE:
                print("vosk loaded")

        except Exception as error:
            self.last_error = str(error)
            self.set_status("error", on_status_change)
            report_error("voice_model", error, operation="voice.vosk.load", context={"engine":"vosk"})

    def audio_callback(self, indata, frames, time, status):
        if status:
            if self.DEBUG_MODE:
                print("audio status:", status)

        raw = bytes(indata)
        if self.noise_suppression:
            raw = self._suppress_noise(raw)
        else:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            rms = math.sqrt(float(np.mean(samples * samples))) if samples.size else 0.0
            self.last_rms = rms
            self.last_block_has_speech = rms >= self.noise_gate
        packet = (raw, self.last_block_has_speech)
        try:
            self.audio_queue.put_nowait(packet)
        except queue.Full:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                pass
            self.audio_queue.put_nowait(packet)

    def _suppress_noise(self, raw_audio):
        samples = np.frombuffer(raw_audio, dtype=np.int16)
        if samples.size == 0:
            return raw_audio

        centered = samples.astype(np.float32)
        centered -= float(np.mean(centered))
        rms = math.sqrt(float(np.mean(centered * centered)))
        self.last_rms = rms
        threshold = max(self.noise_gate, self.noise_floor * self.noise_multiplier)
        self.last_block_has_speech = rms >= threshold

        if self.last_block_has_speech:
            self._speech_blocks_remaining = self.speech_hangover
            return np.clip(centered, -32768, 32767).astype(np.int16).tobytes()

        self.noise_floor = (self.noise_floor * 0.97) + (rms * 0.03)
        if self._speech_blocks_remaining > 0:
            self._speech_blocks_remaining -= 1
            return np.clip(centered, -32768, 32767).astype(np.int16).tobytes()

        # Keep feeding silence so Vosk can close the current phrase cleanly.
        return np.zeros(samples.shape, dtype=np.int16).tobytes()

    def _should_fast_finalize(self, partial_text, silent_blocks):
        return bool(
            self.fast_endpoint
            and partial_text
            and silent_blocks >= self.endpoint_silence_blocks
        )

    def _listen_loop(self, on_final_text=None, on_partial_text=None, on_status_change=None):
        self.load_voice(on_status_change)

        if not self.is_loaded or self._stop_requested.is_set():
            return

        self.is_listening = True

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="int16",
                channels=1,
                callback=self.audio_callback
            ):
                self.set_status("ready", on_status_change)
                if self.DEBUG_MODE:
                    print("voice listening...")

                silent_blocks = 0
                latest_partial = ""
                while self.is_listening and not self._stop_requested.is_set():
                    try:
                        packet = self.audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if isinstance(packet, tuple):
                        data, block_has_speech = packet
                    else:
                        data, block_has_speech = packet, True

                    silent_blocks = 0 if block_has_speech else silent_blocks + 1

                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()

                        if text:
                            if on_status_change:
                                on_status_change("ready")

                            if self.DEBUG_MODE:
                                print("final:", text)

                            if on_final_text:
                                on_final_text(text)
                        latest_partial = ""
                        silent_blocks = 0

                    else:
                        partial = json.loads(self.recognizer.PartialResult())
                        partial_text = partial.get("partial", "").strip()

                        if partial_text:
                            latest_partial = partial_text
                            if on_status_change:
                                on_status_change("hearing")

                            if on_partial_text:
                                on_partial_text(partial_text)

                        if self._should_fast_finalize(latest_partial, silent_blocks):
                            # Let Vosk finish/rescore the utterance instead of executing
                            # a provisional partial (especially important for big models).
                            final_text = json.loads(self.recognizer.FinalResult()).get('text', '').strip() or latest_partial
                            if self.DEBUG_MODE:
                                print("fast final:", final_text)
                            if on_status_change:
                                on_status_change("ready")
                            if on_final_text:
                                on_final_text(final_text)
                            self.recognizer.Reset()
                            latest_partial = ""
                            silent_blocks = 0

        except Exception as error:
            self.last_error = str(error)
            self.set_status("error", on_status_change)

            report_error("voice_runtime", error, operation="voice.capture", context={"engine":"vosk"})

        finally:
            self.is_listening = False
            if self.status != "error":
                self.set_status("idle", on_status_change)

            if self.DEBUG_MODE:
                print("voice stopped")

    def _backend_available(self):
        if vosk is None:
            self._set_vosk_backend_error()
            return False
        return True

    def start_background(self, on_final_text=None, on_partial_text=None, on_status_change=None):
        if self.thread and self.thread.is_alive():
            return not self._stop_requested.is_set()

        if not self._backend_available():
            self.set_status("unavailable", on_status_change)
            return False

        if sd is None:
            self._set_audio_backend_error()
            self.set_status("unavailable", on_status_change)
            return False

        if not self.has_input_device():
            self.set_status("unavailable", on_status_change)
            return False

        self._stop_requested.clear()
        self.last_error = None
        self.thread = threading.Thread(
            target=self._listen_loop,
            kwargs={
                "on_final_text": on_final_text,
                "on_partial_text": on_partial_text,
                "on_status_change": on_status_change
            },
            daemon=True
        )
        self.thread.start()
        return True

    def stop(self):
        self._stop_requested.set()
        self.is_listening = False

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except Exception:
                break
