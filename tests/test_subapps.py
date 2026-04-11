import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.dotenv_values = lambda *args, **kwargs: {}
dotenv_stub.load_dotenv = lambda *args, **kwargs: False
dotenv_stub.set_key = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

from core.process import Process
from helpers.app_launcher import AppLauncher
from helpers.web_assistant import WebAssistant


TEST_APPS = {
    "chrome": {
        "display_name": "Google Chrome",
        "aliases": ["chrome", "google chrome"],
        "command_linux": "google-chrome",
    },
    "steam": {
        "display_name": "Steam",
        "aliases": ["steam"],
        "command_linux": "steam",
        "subapps": {
            "necesse": {
                "display_name": "Necesse",
                "aliases": ["necesse"],
                "target": "steam://rungameid/1169040",
            }
        },
    },
}


class SubappFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.apps_path = Path(self.temp_dir.name) / "apps.json"
        self.apps_path.write_text(json.dumps(TEST_APPS), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def build_process(self):
        process = Process()
        process.app_launcher = AppLauncher(apps_path=str(self.apps_path))
        process.web_assistant = WebAssistant()
        return process

    def test_browser_hosted_site_maps_to_web_action(self):
        process = self.build_process()

        result = process.parse_hosted_app_action("open spotify on chrome")

        self.assertEqual(
            result,
            {
                "kind": "web",
                "mode": "site",
                "query": "spotify",
                "browser_alias": "chrome",
            },
        )

    def test_steam_game_maps_to_subapp_action(self):
        process = self.build_process()

        result = process.parse_hosted_app_action("play necesse in steam")

        self.assertEqual(result["kind"], "subapp")
        self.assertEqual(result["host_key"], "steam")
        self.assertEqual(result["subapp_key"], "necesse")

    def test_spotify_on_browser_stays_web_action_in_detect_patterns(self):
        process = self.build_process()

        patterns = process.detect_patterns("open spotify on chrome")

        self.assertTrue(patterns["web_action"])
        self.assertEqual(patterns["web_mode"], "site")
        self.assertEqual(patterns["web_query"], "spotify")
        self.assertEqual(patterns["web_browser_alias"], "chrome")
        self.assertFalse(patterns["launch_app"])

    def test_launch_subapp_uses_host_command_with_target(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))

        with patch("helpers.app_launcher.subprocess.Popen") as popen:
            success, reason = launcher.launch_subapp("steam", "necesse")

        self.assertTrue(success)
        self.assertIsNone(reason)
        popen.assert_called_once_with(["steam", "steam://rungameid/1169040"])


if __name__ == "__main__":
    unittest.main()
