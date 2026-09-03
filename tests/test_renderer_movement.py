import unittest
from types import SimpleNamespace

from output.renderer import Renderer


class RendererMovementTests(unittest.TestCase):
    def test_cross_monitor_transition_survives_bring_to_front(self):
        renderer = SimpleNamespace(
            current_monitor_index=0,
            current_position_name="top_right",
            monitor_transition_phase=None,
        )
        renderer.refresh_screens = lambda: None

        def bring_to_front():
            renderer.monitor_transition_phase = None

        def compute_location(_position, monitor_index):
            renderer.current_monitor_index = monitor_index
            return 120, 80

        def begin_transition(_x, _y, _monitor_index):
            renderer.monitor_transition_phase = "shrink"

        renderer.bring_to_front = bring_to_front
        renderer._compute_window_location = compute_location
        renderer._begin_monitor_transition = begin_transition
        renderer._set_target_position = lambda *_args: None
        renderer.position_quick_input = lambda: None
        renderer.position_dev_editor = lambda: None

        Renderer.move_overlay(renderer, "current", 1)

        self.assertEqual(renderer.current_monitor_index, 1)
        self.assertEqual(renderer.monitor_transition_phase, "shrink")


if __name__ == "__main__":
    unittest.main()
