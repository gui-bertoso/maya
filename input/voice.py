import json
import queue
import threading
from helpers.config import get_env

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
    def __init__(self, model_path="models/vosk-model-small-en-us-0.15", sample_rate=16000):
        self.model_path = model_path
        self.sample_rate = sample_rate

        self.thread = None
        self.audio_queue = queue.Queue()

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
        return False

    def _set_vosk_backend_error(self, reason=None):
        base_reason = reason or _VOSK_IMPORT_ERROR
        self.last_error = str(base_reason) if base_reason else "vosk is unavailable"
        return False

    def has_input_device(self):
        if sd is None:
            return self._set_audio_backend_error()

        try:
            devices = sd.query_devices()
        except Exception as error:
            self.last_error = str(error)
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
            self.set_status("ready", on_status_change)
            if self.DEBUG_MODE:
                print("vosk loaded")

        except Exception as error:
            self.last_error = str(error)
            self.set_status("error", on_status_change)
            print("voice load error:", repr(error))

    def audio_callback(self, indata, frames, time, status):
        if status:
            if self.DEBUG_MODE:
                print("audio status:", status)

        self.audio_queue.put(bytes(indata))

    def _listen_loop(self, on_final_text=None, on_partial_text=None, on_status_change=None):
        self.load_voice(on_status_change)

        if not self.is_loaded:
            return

        self.is_listening = True

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self.audio_callback
            ):
                if self.DEBUG_MODE:
                    print("voice listening...")

                while self.is_listening:
                    data = self.audio_queue.get()

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

                    else:
                        partial = json.loads(self.recognizer.PartialResult())
                        partial_text = partial.get("partial", "").strip()

                        if partial_text:
                            if on_status_change:
                                on_status_change("hearing")

                            if on_partial_text:
                                on_partial_text(partial_text)

        except Exception as error:
            self.last_error = str(error)
            self.set_status("error", on_status_change)

            print("voice runtime error:", error)

        finally:
            self.is_listening = False
            if self.status != "error":
                self.set_status("ready", on_status_change)

            if self.DEBUG_MODE:
                print("voice stopped")

    def start_background(self, on_final_text=None, on_partial_text=None, on_status_change=None):
        if self.thread and self.thread.is_alive():
            return True

        if vosk is None:
            self._set_vosk_backend_error()
            self.set_status("unavailable", on_status_change)
            return False

        if sd is None:
            self._set_audio_backend_error()
            self.set_status("unavailable", on_status_change)
            return False

        if not self.has_input_device():
            self.set_status("unavailable", on_status_change)
            return False

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
        self.is_listening = False

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except Exception:
                break
