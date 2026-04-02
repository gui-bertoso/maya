import os

class Process:
    def __init__(self):
        self.input_size = 0
        self.input_text = ""
        self.running = True
        self.parent = None

    def run(self):
        while self.running:
            os.system("cls")
            my_input = input(">> ").strip()

            if not my_input:
                continue

            self.input_text = my_input
            self.input_size = len(my_input)

            if my_input == "exit":
                self.running = False
                if self.parent is not None:
                    self.parent.send_event("exit")
                continue

            if self.parent is not None:
                particles_amount = self.parent.get_data("particles_amount") or 0

                if particles_amount < self.input_size:
                    self.parent.send_event(
                        "spawn_particle",
                        self.input_size - particles_amount
                    )
                elif particles_amount > self.input_size:
                    self.parent.send_event(
                        "despawn_particle",
                        particles_amount - self.input_size
                    )