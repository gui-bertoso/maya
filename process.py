import os

class Process:
    def __init__(self):
        self.running = True
        self.parent = None

        self.weights_amount = 128

    def debug_log(self):
        print(f"[fps: {self.parent.get_data("fps")}] - [particles: {self.parent.get_data("particles_amount")}]", end="", flush=True)

    def run(self):
        while self.running:
            my_input = input("\n>> ")

            if not my_input:
                continue

            input_text = my_input

            if my_input == "exit":
                self.running = False
                if self.parent is not None:
                    self.parent.send_event("exit")
                continue

            data_array = self.tokenize(my_input)


            self.update_renderer_particles()

    def update_renderer_particles(self, text):
        input_size = len(text)
        if self.parent is not None:
            particles_amount = self.parent.get_data("particles_amount") or 0

            if particles_amount < input_size:
                self.parent.send_event(
                    "spawn_particle",
                    input_size - particles_amount
                )
            elif particles_amount > input_size:
                self.parent.send_event(
                    "despawn_particle",
                    particles_amount - input_size
                )

    @staticmethod
    def tokenize(value):
        return value.strip()
