from renderer import Renderer
from process import Process
import queue
import vocabulary_manager


class App:
    def __init__(self):
        vocabulary_manager.load_vocabulary()
        self.events = queue.Queue()

        self.process = Process()
        self.process.parent = self

        self.renderer = Renderer(
            self.events,
            submit_input_callback=self.process.handle_input
        )

        self.renderer.run()

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