import pyttsx3
import threading
import queue
import subprocess
import sys
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


class Speaker:
    PIPER_MODEL_MAP = {
        "en": get_resource_path("models/piper/en_US-lessac-high.onnx"),
        "pt": get_resource_path("models/piper/pt_BR-faber-medium.onnx"),
    }

    def __init__(self, rate=180, volume=1.0, voice_id=None, preferred_gender="female", language="en", muted=False, engine_preference="auto"):
        self.rate = rate
        self.volume = volume
        self.voice_id = voice_id
        self.preferred_gender = (preferred_gender or "").strip().lower()
        self.language = (language or "en").strip().lower()
        self.muted = bool(muted)
        self.engine_preference = (engine_preference or "auto").strip().lower()

        self.queue = queue.Queue()
        self.is_running = True
        self.is_speaking = False
        self.active_process = None
        self._piper_voice = None

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    @property
    def use_linux_espeak(self):
        return sys.platform.startswith("linux")

    @property
    def use_piper(self):
        if self.engine_preference == "system":
            return False
        if self.engine_preference == "piper":
            return PiperVoice is not None and sd is not None and self._get_piper_model_path() is not None
        return PiperVoice is not None and sd is not None and self._get_piper_model_path() is not None

    @property
    def use_system_tts(self):
        if self.engine_preference == "piper":
            return not self.use_piper
        return True

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
            self._piper_voice = PiperVoice.load(model_path)
        return self._piper_voice

    def _speak_with_piper(self, text):
        voice = self._get_piper_voice()
        if voice is None:
            raise RuntimeError("piper voice unavailable")

        audio_arrays = []
        sample_rate = None
        for chunk in voice.synthesize(text):
            sample_rate = chunk.sample_rate
            audio_arrays.append(chunk.audio_float_array)

        if not audio_arrays or sample_rate is None:
            return

        import numpy as np

        audio = np.concatenate(audio_arrays)
        audio = audio * max(0.0, min(self.volume, 1.0))
        sd.play(audio, sample_rate)
        sd.wait()

    def _select_linux_voice(self):
        normalized = self.language.replace("_", "-")
        variant = {
            "female": "Annie",
            "male": "Adam",
        }.get(self.preferred_gender, "Annie")

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
            "42" if self.preferred_gender == "female" else "38",
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

        preferred_keywords = {
            "female": ["female", "zira", "hazel", "aria", "susan", "eva", "zira desktop"],
            "male": ["male", "david", "mark", "guy", "george", "james"],
        }

        search_pool = normalized_voices
        if language_matches:
            search_pool = [(voice, searchable) for voice, searchable in normalized_voices if voice in language_matches]

        for keyword in preferred_keywords.get(self.preferred_gender, []):
            for voice, searchable in search_pool:
                if keyword in searchable:
                    engine.setProperty("voice", voice.id)
                    return

        if self.preferred_gender == "female":
            for voice, searchable in search_pool:
                if not any(keyword in searchable for keyword in preferred_keywords["male"]):
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
                    if self.use_piper:
                        self._speak_with_piper(text)
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
