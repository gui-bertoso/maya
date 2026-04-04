from renderer import Renderer
from process import Process
from memory import Memory
from voice import Voice
import queue
import vocabulary_manager
from clap_detector import ClapDetector
import time
import pyglet
from speaker import Speaker


class App:
    def __init__(self):
        vocabulary_manager.load_vocabulary()
        self.events = queue.Queue()

        self.memory = Memory()
        self.memory.load()

        self.process = Process()
        self.process.parent = self
        self.process.memory = self.memory

        self.speaker = Speaker(rate=180)

        self.clap_detector = ClapDetector(
            threshold=150,
            cooldown=0.18,
            double_clap_window=0.75
        )

        self.voice = Voice(
            model_path="models/vosk-model-small-en-us-0.15",
            sample_rate=16000
        )

        self.voice_active = False
        self.wake_duration = 6.0
        self.maya_awake_until = 0.0

        self.renderer = Renderer(
            self.events,
            submit_input_callback=self.handle_input
        )

        self.clap_detector.start(
            on_double_clap=self.handle_double_clap,
            on_clap=self.handle_single_clap
        )

        pyglet.clock.schedule_interval(self.update_app_state, 0.1)

        self.renderer.run()

    def wake_maya(self):
        self.maya_awake_until = time.time() + self.wake_duration

        self.send_event("double_clap", None)
        self.send_event("response_text", "yes?")

        if not self.voice_active:
            self.voice_active = True
            self.voice.start_background(
                on_final_text=self.handle_voice_input,
                on_partial_text=self.handle_partial_voice,
                on_status_change=self.handle_voice_status
            )
        else:
            self.send_event("voice_status", "ready")

    def sleep_maya(self):
        if not self.voice_active:
            return

        self.voice.stop()
        self.voice_active = False
        self.send_event("voice_status", "idle")
        self.send_event("voice_partial", "")
        print("maya sleeping again")

    def update_app_state(self, dt):
        if self.voice_active and time.time() > self.maya_awake_until:
            self.sleep_maya()

    def handle_single_clap(self, rms):
        self.send_event("clap", rms)

    def handle_double_clap(self):
        print("WAKE UP MAYA")
        self.wake_maya()

    def handle_voice_input(self, text):
        self.maya_awake_until = time.time() + self.wake_duration
        self.send_event("voice_final", text)
        return self.handle_input(text)

    def handle_partial_voice(self, text):
        self.speaker.stop()  # 🔥 evita sobreposição
        self.maya_awake_until = time.time() + self.wake_duration
        self.send_event("voice_partial", text)

    def handle_voice_status(self, status):
        if self.voice_active:
            self.send_event("voice_status", status)

    def handle_input(self, text):
        self.maya_awake_until = time.time() + self.wake_duration

        response = self.process.handle_input(text)
        self.memory.save()

        print("input:", repr(text))
        print("response:", repr(response))

        if response:
            self.speaker.stop()
            self.send_event("voice_status", "speaking")
            self.speaker.speak(response)

        return response

    def send_event(self, event, value=None):
        self.events.put((event, value))

    def get_data(self, data):
        if data == "fps":
            return self.renderer.get_fps()
        return None


if __name__ == "__main__":
    App()