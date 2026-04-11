import pyttsx3
import asyncio
import threading
import queue
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from helpers.config import get_resource_path

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    from piper import PiperVoice
except Exception:
    PiperVoice = None

try:
    import edge_tts
except Exception:
    edge_tts = None


class Speaker:
    DEFAULT_GENDER = "female"
    PT_PIPER_PITCH = 1.16
    EDGE_VOICE_MAP = {
        "pt": "pt-BR-FranciscaNeural",
        "en": "en-US-AvaNeural",
    }
    PIPER_MODEL_MAP = {
        "en": get_resource_path("models/piper/en_US-lessac-high.onnx"),
        "pt": get_resource_path("models/piper/pt_BR-cadu-medium.onnx"),
    }

    def __init__(self, rate=180, volume=1.0, voice_id=None, language="en", muted=False, engine_preference="auto"):
        self.rate = rate
        self.volume = volume
        self.voice_id = voice_id
        self.preferred_gender = self.DEFAULT_GENDER
        self.language = (language or "en").strip().lower()
        self.muted = bool(muted)
        self.engine_preference = (engine_preference or "auto").strip().lower()

        self.queue = queue.Queue()
        self.is_running = True
        self.is_speaking = False
        self.active_process = None
        self._piper_voice = None
        self._piper_disabled = False
        self._piper_error = None

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    @property
    def use_linux_espeak(self):
        return sys.platform.startswith("linux")

    @property
    def use_piper(self):
        if self._piper_disabled:
            return False
        if self.engine_preference == "system":
            return False
        if self.use_edge_tts:
            return False
        if self.engine_preference == "piper":
            return PiperVoice is not None and sd is not None and self._get_piper_model_path() is not None
        return PiperVoice is not None and sd is not None and self._get_piper_model_path() is not None

    @property
    def use_system_tts(self):
        if self.engine_preference == "piper":
            return not self.use_piper
        return True

    @property
    def use_edge_tts(self):
        if edge_tts is None:
            return False
        if not sys.platform.startswith("linux"):
            return False

        normalized = self.language.replace("_", "-")
        if self.engine_preference == "edge":
            return True
        if self.engine_preference == "auto" and normalized.startswith("pt"):
            return True
        return False

    def _create_engine(self):
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)

        if self.voice_id:
            engine.setProperty("voice", self.voice_id)
        else:
            self._apply_preferred_voice(engine)

        return engine

    def _get_piper_model_path(self):
        normalized = self.language.replace("_", "-")
        if normalized.startswith("pt"):
            candidate = self.PIPER_MODEL_MAP["pt"]
        else:
            candidate = self.PIPER_MODEL_MAP["en"]

        config_path = Path(f"{candidate}.json")
        if candidate.exists() and config_path.exists():
            return candidate
        return None

    def _get_piper_voice(self):
        model_path = self._get_piper_model_path()
        if model_path is None:
            return None
        if self._piper_voice is None:
            try:
                self._piper_voice = PiperVoice.load(model_path)
            except Exception as error:
                self._piper_disabled = True
                self._piper_error = error
                print(f"piper disabled, falling back to system tts: {error!r}")
                return None
        return self._piper_voice

    def _speak_with_piper(self, text):
        voice = self._get_piper_voice()
        if voice is None:
            return False

        import numpy as np

        audio_arrays = []
        sample_rate = None
        for chunk in voice.synthesize(text):
            sample_rate = chunk.sample_rate
            audio_arrays.append(chunk.audio_float_array)

        if not audio_arrays or sample_rate is None:
            return

        audio = np.concatenate(audio_arrays)
        audio, sample_rate = self._style_piper_audio(audio, sample_rate)
        audio = audio * max(0.0, min(self.volume, 1.0))
        self._play_audio_with_sounddevice(audio, sample_rate)
        return True

    def _style_piper_audio(self, audio, sample_rate):
        if not self.language.replace("_", "-").startswith("pt"):
            return audio, sample_rate

        try:
            return self._shift_audio_pitch(audio, sample_rate, self.PT_PIPER_PITCH)
        except Exception:
            return audio, sample_rate

    def _shift_audio_pitch(self, audio, sample_rate, pitch_scale):
        import numpy as np

        float_audio = np.asarray(audio, dtype=np.float32)
        pcm16 = np.clip(float_audio, -1.0, 1.0)
        pcm16 = (pcm16 * 32767.0).astype(np.int16)

        source_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        target_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        source_path = Path(source_file.name)
        target_path = Path(target_file.name)
        source_file.close()
        target_file.close()

        try:
            with wave.open(str(source_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm16.tobytes())

            command = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source_path),
                "-af",
                f"rubberband=pitch={pitch_scale}:formant=preserved",
                str(target_path),
            ]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            with wave.open(str(target_path), "rb") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                shifted = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
                shifted_rate = wav_file.getframerate()

            return shifted, shifted_rate
        finally:
            for path in (source_path, target_path):
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _play_audio_with_sounddevice(self, audio, sample_rate):
        if sd is None:
            raise RuntimeError("sounddevice unavailable")

        import numpy as np

        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim == 1:
            audio = audio.reshape(-1, 1)

        try:
            sd.check_output_settings(samplerate=sample_rate, channels=audio.shape[1], dtype="float32")
            with sd.OutputStream(
                samplerate=sample_rate,
                channels=audio.shape[1],
                dtype="float32",
                blocksize=2048,
                latency="high",
            ) as stream:
                stream.write(audio)
            return
        except Exception:
            pass

        default_device = sd.query_devices(None, "output")
        target_sample_rate = int(default_device.get("default_samplerate") or sample_rate)
        if target_sample_rate <= 0:
            target_sample_rate = sample_rate

        if target_sample_rate != sample_rate and len(audio) > 1:
            source_positions = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
            target_length = max(1, int(round(len(audio) * (target_sample_rate / sample_rate))))
            target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
            resampled = np.empty((target_length, audio.shape[1]), dtype=np.float32)
            for channel in range(audio.shape[1]):
                resampled[:, channel] = np.interp(target_positions, source_positions, audio[:, channel]).astype(np.float32)
            audio = resampled
            sample_rate = target_sample_rate

        with sd.OutputStream(
            samplerate=sample_rate,
            channels=audio.shape[1],
            dtype="float32",
            blocksize=2048,
            latency="high",
        ) as stream:
            stream.write(audio)

    def _select_linux_voice(self):
        normalized = self.language.replace("_", "-")
        variant = "Annie"

        if normalized.startswith("pt"):
            return f"roa/pt-BR+{variant}"
        if normalized.startswith("en"):
            return f"gmw/en-US+{variant}"
        return variant

    def _speak_with_linux_espeak(self, text):
        # Use espeak-ng directly on Linux so we can control pacing and voice variants
        # better than the default pyttsx3 backend path.
        command = [
            "espeak-ng",
            "-s",
            str(max(120, min(int(self.rate), 185))),
            "-p",
            "42",
            "-a",
            str(max(20, min(int(self.volume * 100), 200))),
            "-g",
            "6",
            "-v",
            self.voice_id or self._select_linux_voice(),
            text,
        ]
        self.active_process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.active_process.wait()
        self.active_process = None

    def _get_edge_voice_name(self):
        normalized = self.language.replace("_", "-")
        if normalized.startswith("pt"):
            return self.EDGE_VOICE_MAP["pt"]
        return self.EDGE_VOICE_MAP["en"]

    def _speak_with_edge_tts(self, text):
        if not self.use_edge_tts:
            return False

        output_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        output_path = Path(output_file.name)
        output_file.close()

        try:
            asyncio.run(
                edge_tts.Communicate(text, voice=self._get_edge_voice_name()).save(str(output_path))
            )
            self.active_process = subprocess.Popen(
                [
                    "ffplay",
                    "-nodisp",
                    "-autoexit",
                    "-loglevel",
                    "error",
                    str(output_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.active_process.wait()
            self.active_process = None
            return True
        finally:
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _language_preferences(self):
        normalized = self.language.replace("_", "-")

        if normalized.startswith("pt"):
            return ["pt-br", "pt", "portuguese", "brazil", "brasil"]
        if normalized.startswith("en"):
            return ["en-us", "en-gb", "english", "america", "britain"]

        base_language = normalized.split("-", 1)[0]
        return [normalized, base_language]

    def _apply_preferred_voice(self, engine):
        try:
            voices = engine.getProperty("voices") or []
        except Exception:
            return

        if not voices:
            return

        normalized_voices = []
        for voice in voices:
            voice_name = getattr(voice, "name", "") or ""
            voice_id = getattr(voice, "id", "") or ""
            voice_languages = getattr(voice, "languages", []) or []
            searchable = " ".join([voice_name, voice_id] + [str(language) for language in voice_languages]).lower()
            normalized_voices.append((voice, searchable))

        language_matches = []
        for keyword in self._language_preferences():
            for voice, searchable in normalized_voices:
                if keyword in searchable and voice not in language_matches:
                    language_matches.append(voice)

        if sys.platform.startswith("linux") and language_matches:
            engine.setProperty("voice", language_matches[0].id)
            return

        preferred_keywords = ["female", "zira", "hazel", "aria", "susan", "eva", "zira desktop"]

        search_pool = normalized_voices
        if language_matches:
            search_pool = [(voice, searchable) for voice, searchable in normalized_voices if voice in language_matches]

        for keyword in preferred_keywords:
            for voice, searchable in search_pool:
                if keyword in searchable:
                    engine.setProperty("voice", voice.id)
                    return

        for voice, searchable in search_pool:
            if "male" not in searchable:
                engine.setProperty("voice", voice.id)
                return

        if language_matches:
            engine.setProperty("voice", language_matches[0].id)

    def _run(self):
        try:
            while self.is_running:
                text = self.queue.get()

                if text is None:
                    break

                text = text.strip()
                if not text:
                    continue

                self.is_speaking = True

                try:
                    spoke_with_edge = False
                    if self.use_edge_tts:
                        spoke_with_edge = self._speak_with_edge_tts(text)

                    if spoke_with_edge:
                        pass
                    else:
                        spoke_with_piper = False
                        if self.use_piper:
                            spoke_with_piper = self._speak_with_piper(text)

                        if spoke_with_piper:
                            pass
                        elif self.use_linux_espeak and self.use_system_tts:
                            self._speak_with_linux_espeak(text)
                        else:
                            engine = None
                            try:
                                # Recreate the engine per utterance to avoid pyttsx3
                                # getting stuck after the first spoken response on Windows.
                                engine = self._create_engine()
                                engine.say(text)
                                engine.runAndWait()
                            finally:
                                try:
                                    if engine:
                                        engine.stop()
                                except Exception:
                                    pass
                except Exception as e:
                    print("tts error:", repr(e))

                self.is_speaking = False

        finally:
            pass

    def speak(self, text):
        if self.muted or not text or not text.strip():
            return

        self.queue.put(text)

    def set_muted(self, muted):
        self.muted = bool(muted)
        if self.muted:
            self.stop()

    def stop(self):
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
        if self.active_process is not None:
            try:
                self.active_process.terminate()
            except Exception:
                pass
            self.active_process = None
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except Exception:
                break

    def shutdown(self):
        self.is_running = False
        self.queue.put(None)
