from renderer import Renderer
from process import Process
import threading
import queue


class App:
    def __init__(self):
        self.events = queue.Queue()

        self.renderer = Renderer(self.events)
        self.process = Process()

        self.process.parent = self

        self.process_thread = threading.Thread(
            target=self.process.run,
            daemon=True
        )
        self.process_thread.start()

        self.renderer.run()

    def send_event(self, event, value=None):
        self.events.put((event, value))

    def get_data(self, data):
        if data == "particles_amount":
            return len(self.renderer.particles)
        if data == "fps":
            return len(self.renderer.get_fps())
        return None
    


if __name__ == "__main__":
    App()