import sys
import types
import unittest

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.dotenv_values = lambda *args, **kwargs: {}
dotenv_stub.load_dotenv = lambda *args, **kwargs: False
dotenv_stub.set_key = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

from core.process import Process
from core.memory import Memory
from helpers.app_text import load_app_text
from helpers.config import ENV_FIELD_MAP
from helpers.spotify_assistant import SpotifyAssistant
from helpers.app_launcher import AppLauncher


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

    def test_greeting_and_memory_hint_are_portuguese(self):
        process = Process()
        process.LANGUAGE = "pt-BR"
        process.responses = {
            "greets_known": ["hey, {user_name}.{memory_hint}"],
            "greets_known_pt": ["oi, {user_name}.{memory_hint}"],
        }

        memory_hint = process._build_memory_hint(["cafe"], ["voce trabalha de casa"])
        response = process.pick_response("greets_known", user_name="Pat", memory_hint=memory_hint)

        self.assertEqual(response, "oi, Pat. eu lembro que voce gosta de cafe e que voce trabalha de casa.")

    def test_common_conversation_response_uses_portuguese_variant(self):
        process = Process()
        process.LANGUAGE = "pt-BR"
        process.responses = {
            "asks_name": ["i'm maya."],
            "asks_name_pt": ["eu sou a maya."],
        }

        response = process.pick_response("asks_name")

        self.assertEqual(response, "eu sou a maya.")

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

    def test_portuguese_extractors_handle_name_preference_and_fact(self):
        self.assertEqual(Process.extract_name("meu nome e pat"), "pat")
        self.assertEqual(Process.extract_preference("eu gosto de cafe"), "cafe")
        self.assertEqual(Process.extract_fact("lembra que eu trabalho de casa"), "eu trabalho de casa")
        self.assertEqual(Process.extract_preference_query("voce lembra que eu gosto de cafe"), "cafe")
        self.assertEqual(Process.extract_fact_query("voce lembra que eu trabalho de casa"), "eu trabalho de casa")

    def test_detect_intent_understands_common_portuguese_tokens(self):
        process = Process()

        self.assertEqual(process.detect_intent(["obrigado"]), "gratitude")
        self.assertEqual(process.detect_intent(["hora"]), "time_question")
        self.assertEqual(process.detect_intent(["desculpa"]), "apology")
        self.assertEqual(process.detect_intent(["tchau"]), "farewell")

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

    def test_spotify_assistant_understands_articles_in_portuguese(self):
        assistant = SpotifyAssistant()

        open_result = assistant.parse_request("abre o spotify")
        track_result = assistant.parse_request("toque eminem no spotify")

        self.assertEqual(open_result["mode"], "app")
        self.assertEqual(track_result["mode"], "track")
        self.assertEqual(track_result["query"], "eminem")

    def test_app_launcher_resolves_alias_with_portuguese_article(self):
        launcher = AppLauncher()

        self.assertEqual(launcher.resolve_alias("o spotify"), "spotify")


class SettingsFieldTests(unittest.TestCase):
    def test_settings_expose_microphone_and_mute_controls(self):
        self.assertIn("MICROPHONE_ENABLED", ENV_FIELD_MAP)
        self.assertIn("SPEECH_MUTED", ENV_FIELD_MAP)
        self.assertIn("APP_TEXT_PATH", ENV_FIELD_MAP)
        self.assertIn("UI_COLOR_IDLE", ENV_FIELD_MAP)
        self.assertIn("UI_COLOR_READY", ENV_FIELD_MAP)
        self.assertIn("UI_COLOR_HEARING", ENV_FIELD_MAP)
        self.assertIn("UI_COLOR_SPEAKING", ENV_FIELD_MAP)
        self.assertIn("UI_COLOR_ERROR", ENV_FIELD_MAP)
        self.assertIn("UI_COLOR_CORE", ENV_FIELD_MAP)
        self.assertNotIn("TTS_VOICE_GENDER", ENV_FIELD_MAP)
        self.assertNotIn("WINDOW_CAPTION", ENV_FIELD_MAP)
        self.assertEqual(ENV_FIELD_MAP["MICROPHONE_ENABLED"].options, ("true", "false"))
        self.assertEqual(ENV_FIELD_MAP["SPEECH_MUTED"].options, ("true", "false"))
        self.assertEqual(ENV_FIELD_MAP["LANGUAGE"].options, ("en", "pt-BR"))

    def test_app_text_json_loads_expected_sections(self):
        app_text = load_app_text()

        self.assertIn("voice_filler_inputs", app_text)
        self.assertIn("startup_greeting_options", app_text)
        self.assertIn("messages", app_text)
        self.assertIn("pt-BR", app_text["startup_greeting_options"])
        self.assertIn("settings_applied", app_text["messages"])

    def test_app_text_has_portuguese_settings_commands(self):
        app_text = load_app_text()
        commands = app_text["settings_commands"]

        self.assertIn("configuracoes", commands)
        self.assertIn("abre configuracoes", commands)
        self.assertIn("me mostra as configuracoes", commands)


class MemoryCleanupTests(unittest.TestCase):
    def test_invalid_preference_noise_is_rejected(self):
        memory = Memory()

        memory.add_preference("to pursue me that tell you keep yourself well as a byproduct of a study of and supplies comes easier")
        memory.add_preference("cafe")

        self.assertEqual(memory.get_preferences(), ["cafe"])


if __name__ == "__main__":
    unittest.main()
