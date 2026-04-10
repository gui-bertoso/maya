import sys
import types
import unittest

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.dotenv_values = lambda *args, **kwargs: {}
dotenv_stub.load_dotenv = lambda *args, **kwargs: False
dotenv_stub.set_key = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

from core.process import Process
from helpers.config import ENV_FIELD_MAP
from helpers.spotify_assistant import SpotifyAssistant


class PortugueseCommandTests(unittest.TestCase):
    def test_pick_response_prefers_portuguese_variant(self):
        process = Process()
        process.LANGUAGE = "pt-BR"
        process.responses = {
            "launch_app_success": ["opening {app_name}."],
            "launch_app_success_pt": ["abrindo {app_name}."],
        }

        response = process.pick_response("launch_app_success", app_name="Spotify")

        self.assertEqual(response, "abrindo Spotify.")

    def test_detect_patterns_understands_portuguese_time_and_search(self):
        process = Process()

        time_patterns = process.detect_patterns("que horas sao")
        search_patterns = process.detect_patterns("procura gatinhos")

        self.assertTrue(time_patterns["asks_time"])
        self.assertTrue(search_patterns["web_action"])
        self.assertEqual(search_patterns["web_mode"], "text")
        self.assertEqual(search_patterns["web_query"], "gatinhos")

    def test_detect_patterns_understands_portuguese_launch_and_close(self):
        process = Process()

        launch_patterns = process.detect_patterns("abrir firefox")
        close_patterns = process.detect_patterns("fechar spotify")

        self.assertTrue(launch_patterns["launch_app"])
        self.assertEqual(launch_patterns["app_alias"], "firefox")
        self.assertTrue(close_patterns["close_app"])
        self.assertEqual(close_patterns["app_alias"], "spotify")

    def test_spotify_assistant_understands_portuguese_track_request(self):
        assistant = SpotifyAssistant()

        result = assistant.parse_request("tocar dua lipa no spotify")

        self.assertEqual(
            result,
            {
                "mode": "track",
                "query": "dua lipa",
                "spoken_query": "dua lipa",
            },
        )


class SettingsFieldTests(unittest.TestCase):
    def test_settings_expose_microphone_and_mute_controls(self):
        self.assertIn("MICROPHONE_ENABLED", ENV_FIELD_MAP)
        self.assertIn("SPEECH_MUTED", ENV_FIELD_MAP)
        self.assertEqual(ENV_FIELD_MAP["MICROPHONE_ENABLED"].options, ("true", "false"))
        self.assertEqual(ENV_FIELD_MAP["SPEECH_MUTED"].options, ("true", "false"))
        self.assertEqual(ENV_FIELD_MAP["LANGUAGE"].options, ("en", "pt-BR"))


if __name__ == "__main__":
    unittest.main()
