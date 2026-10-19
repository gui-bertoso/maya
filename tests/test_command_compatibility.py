import unittest

from core.process import Process
from helpers.spotify_assistant import SpotifyAssistant
from helpers.app_launcher import AppLauncher
from app import App


class CommandCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.process = Process()
        self.process.spotify_assistant = SpotifyAssistant()
        self.process.app_launcher = AppLauncher()

    def assert_command(self, phrase, flag):
        detected = self.process.detect_patterns(phrase)
        self.assertTrue(detected[flag], f"{phrase!r} no longer triggers {flag!r}")

    def test_historically_documented_commands_still_work(self):
        cases = (
            ("me mostra as noticias de hoje", "asks_news"),
            ("abrir spotify no chrome", "web_action"),
            ("tocar dua lipa no spotify", "spotify_action"),
            ("tocar playlist anos 80 no spotify", "spotify_action"),
            ("show open windows", "window_showcase"),
            ("window disco", "window_showcase"),
            ("open firefox", "launch_app"),
            ("close spotify", "close_app"),
        )
        for phrase, flag in cases:
            with self.subTest(phrase=phrase):
                self.assert_command(phrase, flag)

    def test_historic_dev_mode_suggestion_still_works(self):
        app = object.__new__(App)
        self.assertTrue(app._looks_like_dev_mode_suggestion_case("quero codar"))
        self.assertTrue(app._looks_like_dev_mode_suggestion_case("i want to code"))

    def test_window_control_phrases_survive_parser_changes(self):
        cases = (
            "move Discord to another window",
            "move Chrome to the other monitor",
            "mova o Spotify para outra tela",
            "mova o Discord para o outro monitor",
        )
        for phrase in cases:
            with self.subTest(phrase=phrase):
                detected = self.process.detect_patterns(phrase)
                self.assertTrue(detected["move_window"])
                self.assertEqual(detected["move_window_target"]["monitor"], "other")

    def test_move_your_self_moves_maya_instead_of_an_external_window(self):
        for phrase in ("move your self to another window", "move yourself to another window"):
            with self.subTest(phrase=phrase):
                detected = self.process.detect_patterns(phrase)
                self.assertTrue(detected["move_app"])
                self.assertEqual(detected["move_app_target"]["monitor"], "other")
                self.assertFalse(detected["move_window"])


if __name__ == "__main__":
    unittest.main()
