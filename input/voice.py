import json
import queue
import threading
import sounddevice as sd
import vosk
from helpers.config import get_env


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

    def set_status(self, status, on_status_change=None):
        self.status = status
        if on_status_change:
            on_status_change(status)

    def load_voice(self, on_status_change=None):
        if self.is_loaded:
            return

        self.set_status("loading", on_status_change)

        try:
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
            return

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

    def stop(self):
        self.is_listening = False

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except Exception:
                break