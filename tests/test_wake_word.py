import sys
import types
import unittest

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.dotenv_values = lambda *args, **kwargs: {}
dotenv_stub.load_dotenv = lambda *args, **kwargs: False
dotenv_stub.set_key = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

from app import App


class WakeWordTests(unittest.TestCase):
    def make_app(self):
        app = App.__new__(App)
        app.wake_words = ("maya", "maia")
        return app

    def test_name_alone_wakes_without_command(self):
        self.assertEqual(self.make_app()._extract_wake_word_command("Maya"), "")

    def test_name_can_prefix_a_command(self):
        self.assertEqual(
            self.make_app()._extract_wake_word_command("Maya, que horas sao?"),
            "que horas sao",
        )

    def test_un_not_triggered_by_similar_conversation(self):
        self.assertIsNone(self.make_app()._extract_wake_word_command("amanha eu vejo isso"))

    def test_alias_maia_is_supported_for_speech_recognition(self):
        self.assertEqual(self.make_app()._extract_wake_word_command("Maia abre o Spotify"), "abre o spotify")


if __name__ == "__main__":
    unittest.main()
