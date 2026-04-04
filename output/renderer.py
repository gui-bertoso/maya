import math
import pyglet
from pyglet import gl
from pyglet.window import key


class MayaRing:
    def __init__(self, x, y, radius=110, thickness=24, points=96):
        self.x = x
        self.y = y

        self.base_radius = radius
        self.base_thickness = thickness
        self.points = points

        self.time = 0.0
        self.energy = 0.0
        self.target_energy = 2.0

        self.state = "idle"
        self.state_timer = 0.0

        self.base_color = (255, 255, 255)
        self.state_color = (255, 255, 255)

    def set_state(self, state, duration=0.0):
        self.state = state
        self.state_timer = duration

        if state == "idle":
            self.target_energy = 1.8
            self.state_color = (255, 255, 255)

        elif state == "ready":
            self.target_energy = 4.0
            self.state_color = (100, 255, 140)

        elif state == "hearing":
            self.target_energy = 14.0
            self.state_color = (255, 220, 90)

        elif state == "speaking":
            self.target_energy = 9.0
            self.state_color = (100, 180, 255)

        elif state == "error":
            self.target_energy = 8.0
            self.state_color = (255, 90, 90)

        elif state == "wake":
            self.target_energy = 22.0
            self.state_color = (180, 120, 255)

        else:
            self.target_energy = 3.0
            self.state_color = (220, 220, 220)

    def update(self, dt):
        self.time += dt
        self.energy += (self.target_energy - self.energy) * min(dt * 7.0, 1.0)

        if self.state_timer > 0.0:
            self.state_timer -= dt
            if self.state_timer <= 0.0:
                if self.state in ("wake", "speaking"):
                    self.set_state("ready")

    def get_ring_points(self, radius_offset=0.0, thickness=20.0, wave_scale=1.0, time_offset=0.0):
        outer = []
        inner = []

        for i in range(self.points):
            angle = (i / self.points) * math.pi * 2.0

            wave1 = math.sin(angle * 3.0 + (self.time + time_offset) * 1.8) * (self.energy * 1.0 * wave_scale)
            wave2 = math.sin(angle * 5.0 - (self.time + time_offset) * 1.25) * (self.energy * 0.45 * wave_scale)
            wave3 = math.sin(angle * 2.0 + (self.time + time_offset) * 0.7) * 1.5

            radius = self.base_radius + radius_offset + wave1 + wave2 + wave3

            outer_radius = radius
            inner_radius = radius - thickness

            ox = self.x + math.cos(angle) * outer_radius
            oy = self.y + math.sin(angle) * outer_radius
            ix = self.x + math.cos(angle) * inner_radius
            iy = self.y + math.sin(angle) * inner_radius

            outer.append((ox, oy))
            inner.append((ix, iy))

        return outer, inner

    def draw_ring(self, radius_offset, thickness, color, opacity=255, wave_scale=1.0, time_offset=0.0):
        outer, inner = self.get_ring_points(
            radius_offset=radius_offset,
            thickness=thickness,
            wave_scale=wave_scale,
            time_offset=time_offset
        )

        vertices = []
        colors = []

        for i in range(self.points):
            j = (i + 1) % self.points

            ox1, oy1 = outer[i]
            ox2, oy2 = outer[j]
            ix1, iy1 = inner[i]
            ix2, iy2 = inner[j]

            vertices.extend([
                ox1, oy1, 0.0,
                ox2, oy2, 0.0,
                ix1, iy1, 0.0,
            ])

            vertices.extend([
                ix1, iy1, 0.0,
                ox2, oy2, 0.0,
                ix2, iy2, 0.0,
            ])

            for _ in range(6):
                colors.extend([color[0], color[1], color[2], opacity])

        pyglet.graphics.draw(
            len(vertices) // 3,
            gl.GL_TRIANGLES,
            position=("f", vertices),
            colors=("Bn", colors)
        )

    def draw(self):
        self.draw_ring(
            radius_offset=26,
            thickness=10,
            color=self.state_color,
            opacity=26,
            wave_scale=1.2,
            time_offset=1.2
        )

        self.draw_ring(
            radius_offset=14,
            thickness=5,
            color=self.state_color,
            opacity=90,
            wave_scale=1.15,
            time_offset=0.8
        )

        self.draw_ring(
            radius_offset=0,
            thickness=self.base_thickness,
            color=self.base_color,
            opacity=255,
            wave_scale=1.0,
            time_offset=0.0
        )

        self.draw_ring(
            radius_offset=-14,
            thickness=6,
            color=self.state_color,
            opacity=120,
            wave_scale=0.65,
            time_offset=0.35
        )


class Renderer:
    def __init__(self, events, submit_input_callback):
        self.events = events
        self.submit_input_callback = submit_input_callback

        self.window_size_x = 900
        self.window_size_y = 700

        self.window = pyglet.window.Window(
            self.window_size_x,
            self.window_size_y,
            caption="maya",
            vsync=True
        )

        self.live_input = ""
        self.heard_text = ""
        self.response_text = ""
        self.voice_status = "idle"

        self.ring = MayaRing(
            x=self.window_size_x // 2,
            y=self.window_size_y // 2 + 30,
            radius=105,
            thickness=24,
            points=100
        )
        self.ring.set_state("idle")

        self.status_label = pyglet.text.Label(
            "idle",
            x=self.window_size_x // 2,
            y=120,
            anchor_x="center",
            anchor_y="center",
            color=(170, 170, 170, 255),
            font_size=12
        )

        self.heard_label = pyglet.text.Label(
            "",
            x=self.window_size_x // 2,
            y=90,
            anchor_x="center",
            anchor_y="center",
            color=(130, 130, 130, 255),
            font_size=10
        )

        self.response_label = pyglet.text.Label(
            "",
            x=self.window_size_x // 2,
            y=60,
            anchor_x="center",
            anchor_y="center",
            color=(210, 210, 210, 255),
            font_size=11
        )

        self.input_label = pyglet.text.Label(
            "> ",
            x=self.window_size_x // 2,
            y=28,
            anchor_x="center",
            anchor_y="center",
            color=(255, 255, 255, 255),
            font_size=12
        )

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
        self.input_label.text = f"> {display_value}"

    def set_voice_status(self, status):
        self.voice_status = status
        self.status_label.text = status

        if status == "loading":
            self.status_label.color = (255, 120, 120, 255)
            self.ring.set_state("idle")

        elif status == "ready":
            self.status_label.color = (120, 255, 160, 255)
            self.ring.set_state("ready")

        elif status == "hearing":
            self.status_label.color = (255, 220, 120, 255)
            self.ring.set_state("hearing")

        elif status == "error":
            self.status_label.color = (255, 100, 100, 255)
            self.ring.set_state("error")

        else:
            self.status_label.color = (170, 170, 170, 255)
            self.ring.set_state("idle")

    def set_voice_partial(self, text):
        display_value = text[:60] + "..." if len(text) > 60 else text
        self.heard_label.text = display_value

    def clear_voice_partial(self):
        self.heard_label.text = ""

    def set_response_text(self, text):
        display_value = text[:72] + "..." if len(text) > 72 else text
        self.response_label.text = display_value
        self.ring.set_state("speaking", duration=0.6)

    def trigger_wake(self):
        self.ring.set_state("wake", duration=0.45)

    def handle_events(self):
        while not self.events.empty():
            event, value = self.events.get()

            if event == "voice_status":
                self.set_voice_status(value)

            elif event == "voice_partial":
                self.set_voice_partial(value)

            elif event == "voice_final":
                self.clear_voice_partial()

            elif event == "response_text":
                self.set_response_text(value)

            elif event == "double_clap":
                self.trigger_wake()

            elif event == "input_text":
                pass

            elif event == "intent":
                pass

            elif event == "set_particles":
                pass

            elif event == "exit":
                pyglet.app.exit()

    def draw_scene(self):
        self.window.clear()
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)

        self.ring.draw()
        self.status_label.draw()
        self.heard_label.draw()
        self.response_label.draw()
        self.input_label.draw()

    def update(self, dt):
        self.handle_events()
        self.ring.update(dt)

    def run(self):
        pyglet.clock.schedule_interval(self.update, 1 / 60)
        pyglet.app.run()

    def get_fps(self):
        return "vsync"