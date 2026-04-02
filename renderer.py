import pyglet
from pyglet import shapes
import random


class Renderer:
    def __init__(self, events):
        self.events = events

        self.window = pyglet.window.Window(800, 600, "maya", vsync=False)

        self.batch = pyglet.graphics.Batch()
        self.particles = []

        @self.window.event
        def on_draw():
            self.window.clear()
            self.batch.draw()

    def run(self):
        pyglet.clock.schedule_interval(self.update, 1 / 60)
        pyglet.app.run()

    def update(self, dt):
        self.handle_events()
        self.apply_physics(dt)

    def handle_events(self):
        while not self.events.empty():
            event, value = self.events.get()

            if event == "spawn_particle":
                self.spawn_particles(value)

            elif event == "despawn_particle":
                self.despawn_particles(value)

            elif event == "exit":
                pyglet.app.exit()

    def spawn_particles(self, amount, x=400, y=300):
        for _ in range(amount):
            p = shapes.Circle(
                x,
                y,
                4,
                color=(255, 255, 255),
                batch=self.batch
            )
            p.vx = random.uniform(-50, 50)
            p.vy = random.uniform(-50, 50)
            self.particles.append(p)

    def despawn_particles(self, amount):
        amount = min(amount, len(self.particles))

        for _ in range(amount):
            p = self.particles.pop()
            p.delete()

    def apply_physics(self, dt):
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt

            if p.x < 0 or p.x > 800:
                p.vx *= -1
            if p.y < 0 or p.y > 600:
                p.vy *= -1