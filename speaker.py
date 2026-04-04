import pyttsx3
import threading
import queue


class Speaker:
    def __init__(self, rate=180, volume=1.0, voice_id=None):
        self.rate = rate
        self.volume = volume
        self.voice_id = voice_id

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

        return engine

    def _run(self):
        engine = None

        try:
            engine = self._create_engine()

            while self.is_running:
                text = self.queue.get()

                if text is None:
                    break

                text = text.strip()
                if not text:
                    continue

                self.is_speaking = True

                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception as e:
                    print("tts error:", repr(e))

                self.is_speaking = False

        finally:
            try:
                if engine:
                    engine.stop()
            except Exception:
                pass

    def speak(self, text):
        if not text or not text.strip():
            return

        self.queue.put(text)

    def stop(self):
        # limpa fila pendente
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except Exception:
                break

    def shutdown(self):
        self.is_running = False
        self.queue.put(None)