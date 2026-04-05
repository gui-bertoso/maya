import pyttsx3
import threading
import queue


class Speaker:
    def __init__(self, rate=180, volume=1.0, voice_id=None, preferred_gender="female"):
        self.rate = rate
        self.volume = volume
        self.voice_id = voice_id
        self.preferred_gender = (preferred_gender or "").strip().lower()

        self.queue = queue.Queue()
        self.is_running = True
        self.is_speaking = False

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _create_engine(self):
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)

        if self.voice_id:
            engine.setProperty("voice", self.voice_id)
        else:
            self._apply_preferred_voice(engine)

        return engine

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

        preferred_keywords = {
            "female": ["female", "zira", "hazel", "aria", "susan", "eva", "zira desktop"],
            "male": ["male", "david", "mark", "guy", "george", "james"],
        }

        for keyword in preferred_keywords.get(self.preferred_gender, []):
            for voice, searchable in normalized_voices:
                if keyword in searchable:
                    engine.setProperty("voice", voice.id)
                    return

        if self.preferred_gender == "female":
            for voice, searchable in normalized_voices:
                if not any(keyword in searchable for keyword in preferred_keywords["male"]):
                    engine.setProperty("voice", voice.id)
                    return

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

                engine = None
                try:
                    # Recreate the engine per utterance to avoid pyttsx3
                    # getting stuck after the first spoken response on Windows.
                    engine = self._create_engine()
                    engine.say(text)
                    engine.runAndWait()
                except Exception as e:
                    print("tts error:", repr(e))
                finally:
                    try:
                        if engine:
                            engine.stop()
                    except Exception:
                        pass

                self.is_speaking = False

        finally:
            pass

    def speak(self, text):
        if not text or not text.strip():
            return

        self.queue.put(text)

    def stop(self):
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except Exception:
                break

    def shutdown(self):
        self.is_running = False
        self.queue.put(None)
