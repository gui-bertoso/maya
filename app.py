from renderer import Renderer
from process import Process
from memory import Memory
from voice import Voice
import queue
import vocabulary_manager


class App:
    def __init__(self):
        vocabulary_manager.load_vocabulary()
        self.events = queue.Queue()

        self.memory = Memory()
        self.memory.load()

        self.process = Process()
        self.process.parent = self
        self.process.memory = self.memory

        self.voice = Voice(
            model_path="models/vosk-model-small-en-us-0.15",
            sample_rate=16000
        )

        self.renderer = Renderer(
            self.events,
            submit_input_callback=self.handle_input
        )

        self.voice.start_background(
            on_final_text=self.handle_voice_input,
            on_partial_text=self.handle_partial_voice,
            on_status_change=self.handle_voice_status
        )

        self.renderer.run()

    def handle_voice_input(self, text):
        self.send_event("voice_final", text)
        return self.handle_input(text)

    def handle_partial_voice(self, text):
        self.send_event("voice_partial", text)

    def handle_voice_status(self, status):
        self.send_event("voice_status", status)

    def handle_input(self, text):
        response = self.process.handle_input(text)
        self.memory.save()
        return response

    def send_event(self, event, value=None):
        self.events.put((event, value))

    def get_data(self, data):
        if data == "particles_amount":
            return len(self.renderer.particles)
        if data == "fps":
            return self.renderer.get_fps()
        return None


if __name__ == "__main__":
    App()