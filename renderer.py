import random
import pyglet
from pyglet import shapes
from pyglet.window import key


class Renderer:
    def __init__(self, events, submit_input_callback):
        self.events = events
        self.submit_input_callback = submit_input_callback

        self.grid_width = 30
        self.grid_height = 30

        self.attraction_grid = [
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 2, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 2, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 2, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 1, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 1, 0, 0, 0, 0,
            0, 0, 1, 1, 1, 0, 0, 0, 0, 0,
        ]

        self.particles = []
        self.grid_points = []
        self.active_points = []

        self.current_intent = "unknown"
        self.intent_force_multiplier = 1.0
        self.intent_damping = 0.82

        self.particle_radius = 4
        self.grid_size = 10
        self.interference_radius = 60

        self.input_text_value = ""
        self.intent_text_value = ""
        self.response_text_value = ""
        self.live_input = ""

        self.window_size_x = 800
        self.window_size_y = 600

        self.window = pyglet.window.Window(
            self.window_size_x,
            self.window_size_y,
            caption="maya",
            vsync=False
        )

        self.fps_label = pyglet.window.FPSDisplay(self.window)

        self.particles_batch = pyglet.graphics.Batch()
        self.grid_batch = pyglet.graphics.Batch()
        self.grid_points_batch = pyglet.graphics.Batch()
        self.hud_bg_batch = pyglet.graphics.Batch()
        self.hud_batch = pyglet.graphics.Batch()

        self.hud_background = shapes.Rectangle(
            x=0,
            y=0,
            width=420,
            height=170,
            color=(8, 12, 18),
            batch=self.hud_bg_batch
        )
        self.hud_background.opacity = 190

        self.input_label = pyglet.text.Label(
            "input: ",
            x=12,
            y=92,
            anchor_x="left",
            anchor_y="bottom",
            color=(255, 255, 255, 255),
            batch=self.hud_batch
        )

        self.intent_label = pyglet.text.Label(
            "intent: ",
            x=12,
            y=66,
            anchor_x="left",
            anchor_y="bottom",
            color=(100, 255, 100, 255),
            batch=self.hud_batch
        )

        self.response_label = pyglet.text.Label(
            "response: ",
            x=12,
            y=40,
            anchor_x="left",
            anchor_y="bottom",
            color=(100, 180, 255, 255),
            batch=self.hud_batch
        )

        self.live_input_label = pyglet.text.Label(
            "> ",
            x=12,
            y=12,
            anchor_x="left",
            anchor_y="bottom",
            color=(255, 220, 120, 255),
            batch=self.hud_batch
        )

        self.voice_status_value = "idle"
        self.voice_partial_value = ""

        self.voice_label = pyglet.text.Label(
            "voice: idle",
            x=12,
            y=118,
            anchor_x="left",
            anchor_y="bottom",
            color=(255, 120, 120, 255),
            batch=self.hud_batch
        )

        self.voice_partial_label = pyglet.text.Label(
            "heard: ",
            x=12,
            y=144,
            anchor_x="left",
            anchor_y="bottom",
            color=(180, 255, 180, 255),
            batch=self.hud_batch
        )
        self.voice_indicator = shapes.Circle(
            x=390,
            y=145,
            radius=10,
            color=(255, 0, 0),
            batch=self.hud_batch
        )
        self.voice_indicator.opacity = 220

        @self.window.event
        def on_draw():
            self.draw_scene()

        @self.window.event
        def on_text(text):
            if text in ("\r", "\n"):
                return

            if text.isprintable():
                self.live_input += text
                self.update_live_input_label()

        @self.window.event
        def on_key_press(symbol, modifiers):
            if symbol == key.BACKSPACE:
                self.live_input = self.live_input[:-1]
                self.update_live_input_label()

            elif symbol == key.ENTER:
                submitted_text = self.live_input.strip()

                if submitted_text:
                    if submitted_text == "exit":
                        pyglet.app.exit()
                        return

                    self.submit_input_callback(submitted_text)

                self.live_input = ""
                self.update_live_input_label()

    def update_live_input_label(self):
        display_value = self.live_input[:70] + "..." if len(self.live_input) > 70 else self.live_input
        self.live_input_label.text = f"> {display_value}"

    def set_voice_status(self, status):
        self.voice_status_value = status
        self.voice_label.text = f"voice: {status}"

        if status == "loading":
            self.voice_indicator.color = (255, 60, 60)
            self.voice_label.color = (255, 120, 120, 255)

        elif status == "ready":
            self.voice_indicator.color = (60, 255, 100)
            self.voice_label.color = (120, 255, 120, 255)

        elif status == "hearing":
            self.voice_indicator.color = (255, 220, 80)
            self.voice_label.color = (255, 220, 120, 255)

        elif status == "error":
            self.voice_indicator.color = (120, 120, 120)
            self.voice_label.color = (180, 180, 180, 255)

        else:
            self.voice_indicator.color = (255, 0, 0)
            self.voice_label.color = (255, 120, 120, 255)

    def set_voice_partial(self, text):
        self.voice_partial_value = text
        display_value = text[:50] + "..." if len(text) > 50 else text
        self.voice_partial_label.text = f"heard: {display_value}"

    def clear_voice_partial(self):
        self.voice_partial_value = ""
        self.voice_partial_label.text = "heard: "

    def run(self):
        self.create_grid()
        pyglet.clock.schedule_interval(self.update, 1 / 60)
        pyglet.app.run()

    def get_fps(self):
        return self.fps_label.label.text

    def set_intent_state(self, intent):
        self.current_intent = intent

        if intent == "greeting":
            self.intent_force_multiplier = 1.35
            self.intent_damping = 0.88

        elif intent == "farewell":
            self.intent_force_multiplier = -0.35
            self.intent_damping = 0.96

        elif intent == "status_question":
            self.intent_force_multiplier = 0.55
            self.intent_damping = 0.90

        else:
            self.intent_force_multiplier = 1.0
            self.intent_damping = 0.82

    def draw_scene(self):
        self.window.clear()
        self.grid_batch.draw()
        self.grid_points_batch.draw()
        self.particles_batch.draw()
        self.hud_bg_batch.draw()
        self.hud_batch.draw()
        self.fps_label.draw()

    def update(self, dt):
        self.handle_events()
        self.apply_interference_radius(dt)
        self.apply_particles_repulsion()
        self.apply_particles_physics(dt)

    def handle_events(self):
        while not self.events.empty():
            event, value = self.events.get()

            if event == "set_particles":
                self.set_particles(value)

            elif event == "intent":
                self.set_intent_state(value)
                self.intent_text_value = value
                self.intent_label.text = f"intent: {value}"

            elif event == "input_text":
                self.input_text_value = value
                display_value = value[:70] + "..." if len(value) > 70 else value
                self.input_label.text = f"input: {display_value}"

            elif event == "response_text":
                self.response_text_value = value
                display_value = value[:70] + "..." if len(value) > 70 else value
                self.response_label.text = f"response: {display_value}"

            elif event == "voice_status":
                self.set_voice_status(value)

            elif event == "voice_partial":
                self.set_voice_partial(value)

            elif event == "voice_final":
                self.clear_voice_partial()

            elif event == "exit":
                pyglet.app.exit()

    def apply_particles_physics(self, dt):
        for particle in self.particles:
            particle.vx *= self.intent_damping
            particle.vy *= self.intent_damping

            particle.x += particle.vx * min(dt * 60.0, 2.0)
            particle.y += particle.vy * min(dt * 60.0, 2.0)

    def apply_particles_repulsion(self):
        min_dist = self.particle_radius * 2.2
        min_dist_sq = min_dist * min_dist
        push_strength = 0.25

        for i in range(len(self.particles)):
            p1 = self.particles[i]
            for j in range(i + 1, len(self.particles)):
                p2 = self.particles[j]

                dx = p2.x - p1.x
                dy = p2.y - p1.y
                dist_sq = dx * dx + dy * dy

                if dist_sq == 0:
                    dx = random.uniform(-1.0, 1.0)
                    dy = random.uniform(-1.0, 1.0)
                    dist_sq = dx * dx + dy * dy + 0.0001

                if dist_sq < min_dist_sq:
                    dist = dist_sq ** 0.5
                    nx = dx / dist
                    ny = dy / dist

                    overlap = min_dist - dist
                    push = overlap * push_strength * 0.5

                    p1.x -= nx * push
                    p1.y -= ny * push
                    p2.x += nx * push
                    p2.y += ny * push

    def apply_interference_radius(self, dt):
        for _, circle, value in self.active_points:
            cx, cy = circle.x, circle.y
            radius = circle.radius
            radius_sq = radius * radius

            for particle in self.particles:
                dx = cx - particle.x
                dy = cy - particle.y
                dist_sq = dx * dx + dy * dy

                if 0 < dist_sq <= radius_sq:
                    dist = dist_sq ** 0.5
                    falloff = 1.0 - (dist / radius)
                    force = falloff * value * 0.18 * self.intent_force_multiplier

                    particle.vx += dx * force * dt * 60.0
                    particle.vy += dy * force * dt * 60.0

    def create_grid(self):
        self.grid_points.clear()
        self.active_points.clear()

        cell_width = self.window_size_x / self.grid_size
        cell_height = self.window_size_y / self.grid_size

        for y in range(self.grid_size):
            for x in range(self.grid_size):
                pos_x = x * cell_width + cell_width / 2
                pos_y = (self.grid_size - 1 - y) * cell_height + cell_height / 2

                index = y * self.grid_size + x
                value = self.attraction_grid[index]

                circle = shapes.Circle(
                    x=pos_x,
                    y=pos_y,
                    radius=max(1, self.interference_radius * value),
                    color=(255, 255, 255),
                    batch=self.grid_points_batch,
                )
                circle.opacity = 12 if value > 0 else 0

                label = pyglet.text.Label(
                    str(value),
                    x=pos_x,
                    y=pos_y,
                    anchor_x="center",
                    anchor_y="center",
                    batch=self.grid_batch,
                    color=self.get_color_per_force(value),
                )

                item = (label, circle, value)
                self.grid_points.append(item)

                if value > 0:
                    self.active_points.append(item)

    @staticmethod
    def get_particle_color(particle_type):
        if particle_type == "vocab":
            return (0, 255, 0)
        return (255, 255, 255)

    def set_particles(self, particle_types, x=400, y=300):
        current_amount = len(self.particles)
        target_amount = len(particle_types)

        if current_amount < target_amount:
            for _ in range(target_amount - current_amount):
                particle = shapes.Circle(
                    x, y,
                    self.particle_radius,
                    color=(255, 255, 255),
                    batch=self.particles_batch
                )
                particle.vx = 0.0
                particle.vy = 0.0
                self.particles.append(particle)

        elif current_amount > target_amount:
            for _ in range(current_amount - target_amount):
                particle = self.particles.pop()
                particle.delete()

        for particle, particle_type in zip(self.particles, particle_types):
            particle.color = self.get_particle_color(particle_type)

            if self.current_intent == "greeting":
                particle.opacity = 255
            elif self.current_intent == "farewell":
                particle.opacity = 170
            elif self.current_intent == "status_question":
                particle.opacity = 210
            else:
                particle.opacity = 255

    @staticmethod
    def get_color_per_force(force):
        match force:
            case 1:
                return 120, 255, 120, 180
            case 2:
                return 255, 255, 120, 180
            case 3:
                return 255, 120, 120, 180
            case _:
                return 180, 180, 180, 70