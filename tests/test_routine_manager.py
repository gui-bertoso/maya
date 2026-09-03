import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from core.routine_manager import RoutineManager


class RoutineManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "routine.json"
        self.now = datetime(2026, 9, 2, 12, 30)
        self.manager = RoutineManager(self.path, now_provider=lambda: self.now)

    def tearDown(self):
        self.temp.cleanup()

    def test_switches_between_both_routines_and_persists(self):
        self.manager.handle_command("!routine b")
        loaded = RoutineManager(self.path, now_provider=lambda: self.now)
        self.assertEqual(loaded.data["active_routine"], "b")
        self.assertIn("14:00", loaded.format_today())

    def test_done_awards_xp_only_once(self):
        first = self.manager.handle_command("!done rust")
        second = self.manager.handle_command("!done rust")
        self.assertIn("+100 XP", first)
        self.assertIn("+0 XP", second)
        self.assertEqual(self.manager.stats()["xp"], 100)

    def test_skip_changes_status_without_xp(self):
        self.manager.handle_command("!skip english")
        self.assertEqual(self.manager.stats()["skipped"], 1)
        self.assertEqual(self.manager.stats()["xp"], 0)

    def test_late_wakeup_preserves_fixed_school(self):
        response = self.manager.handle_command("acordei as 09:20")
        schedule = self.manager.schedule()
        school = next(task for task in schedule if task["key"] == "school")
        self.assertIn("recalculado", response)
        self.assertEqual(school["start"], "18:30")
        self.assertEqual(schedule[0]["start"], "09:20")

    def test_reminder_fires_once(self):
        reminders = self.manager.due_reminders()
        self.assertEqual(len(reminders), 1)
        self.assertEqual(self.manager.due_reminders(), [])

    def test_week_and_status_are_available(self):
        self.manager.handle_command("!done work")
        self.assertIn("100", self.manager.handle_command("!status"))
        self.assertIn("Total: 100 XP", self.manager.handle_command("!week"))


if __name__ == "__main__":
    unittest.main()
