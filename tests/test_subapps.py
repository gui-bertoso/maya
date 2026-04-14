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

    def test_unknown_steam_game_still_maps_to_subapp_action(self):
        process = self.build_process()

        result = process.parse_hosted_app_action("play hades in steam")

        self.assertEqual(result["kind"], "subapp")
        self.assertEqual(result["host_key"], "steam")
        self.assertEqual(result["subapp_alias"], "hades")

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

    def test_find_installed_app_target_prefers_matching_exe(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "windows"

        with tempfile.TemporaryDirectory() as temp_dir:
            game_dir = Path(temp_dir) / "Hades"
            game_dir.mkdir()
            exe_path = game_dir / "Hades.exe"
            exe_path.write_text("", encoding="utf-8")

            with patch.object(launcher, "_get_windows_search_roots", return_value=[temp_dir]):
                result = launcher.find_installed_app_target("hades")

        self.assertEqual(result, str(exe_path))

    def test_windows_discovery_stops_after_directory_budget(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "windows"
        launcher.DISCOVERY_MAX_DIRECTORIES = 2
        visited = []

        def fake_walk(_root):
            for index in range(10):
                visited.append(index)
                yield (f"/fake/root/{index}", [], [])

        with patch.object(launcher, "_get_windows_search_roots", return_value=["/fake/root"]):
            with patch("helpers.app_launcher.os.walk", side_effect=fake_walk):
                result = launcher.find_installed_app_target("missing app")

        self.assertIsNone(result)
        self.assertEqual(len(visited), 2)

    def test_launch_subapp_falls_back_to_discovered_steam_game(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))

        with patch.object(launcher, "launch_discovered_app", return_value=(True, None)) as discovered:
            success, reason = launcher.launch_subapp("steam", "hades")

        self.assertTrue(success)
        self.assertIsNone(reason)
        discovered.assert_called_once_with("hades", prefer_steam=True)

    def test_launch_any_uses_discovered_windows_app_before_shell_start(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "windows"

        with patch.object(launcher, "launch_discovered_app", return_value=(True, None)) as discovered:
            with patch("helpers.app_launcher.subprocess.Popen") as popen:
                success, reason = launcher.launch_any("elden ring")

        self.assertTrue(success)
        self.assertIsNone(reason)
        discovered.assert_called_once_with("elden ring")
        popen.assert_not_called()

    def test_find_installed_app_target_reads_linux_desktop_entries(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "linux"

        with tempfile.TemporaryDirectory() as temp_dir:
            desktop_path = Path(temp_dir) / "org.supergame.Hades.desktop"
            desktop_path.write_text(
                "[Desktop Entry]\nName=Hades\nExec=/opt/Hades/hades.sh %U\nType=Application\n",
                encoding="utf-8",
            )

            with patch.object(launcher, "_get_linux_search_roots", return_value=[temp_dir]):
                with patch.object(launcher, "_find_steam_manifest_target", return_value=None):
                    result = launcher.find_installed_app_target("hades")

        self.assertEqual(result, str(desktop_path))

    def test_launch_discovered_linux_desktop_executes_desktop_command(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "linux"

        with tempfile.TemporaryDirectory() as temp_dir:
            desktop_path = Path(temp_dir) / "org.supergame.Hades.desktop"
            desktop_path.write_text(
                "[Desktop Entry]\nName=Hades\nExec=/opt/Hades/hades.sh --fullscreen %U\nType=Application\n",
                encoding="utf-8",
            )

            with patch.object(launcher, "find_installed_app_target", return_value=str(desktop_path)):
                with patch("helpers.app_launcher.subprocess.Popen") as popen:
                    with patch("helpers.app_launcher.shutil.which", return_value=None):
                        success, reason = launcher.launch_discovered_app("hades")

        self.assertTrue(success)
        self.assertIsNone(reason)
        popen.assert_called_once_with(["/opt/Hades/hades.sh", "--fullscreen"])

    def test_find_installed_app_target_uses_linux_steam_manifest(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "linux"

        with patch.object(launcher, "_find_steam_manifest_target", return_value="steam://rungameid/1145360"):
            result = launcher.find_installed_app_target("hades", prefer_steam=True)

        self.assertEqual(result, "steam://rungameid/1145360")

    def test_find_installed_app_target_uses_steam_manifest_without_explicit_steam_host(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "windows"

        with patch.object(launcher, "_find_steam_manifest_target", return_value="steam://rungameid/632360") as manifest:
            with patch.object(launcher, "_discover_windows_candidates") as discover:
                result = launcher.find_installed_app_target("risk of rain 2")

        self.assertEqual(result, "steam://rungameid/632360")
        manifest.assert_called_once_with("risk of rain 2")
        discover.assert_not_called()

    def test_find_installed_app_target_reads_windows_steam_manifest_from_registry_root(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "windows"

        with tempfile.TemporaryDirectory() as temp_dir:
            steamapps_dir = Path(temp_dir) / "steamapps"
            steamapps_dir.mkdir()
            manifest_path = steamapps_dir / "appmanifest_632360.acf"
            manifest_path.write_text(
                '"AppState"\n{\n    "appid"    "632360"\n    "name"    "Risk of Rain 2"\n}\n',
                encoding="utf-8",
            )

            with patch.object(launcher, "_get_windows_steam_registry_paths", return_value=[temp_dir]):
                result = launcher.find_installed_app_target("risk of rain 2")

        self.assertEqual(result, "steam://rungameid/632360")

    def test_launch_any_uses_discovered_linux_app_before_direct_exec(self):
        launcher = AppLauncher(apps_path=str(self.apps_path))
        launcher.platform_key = "linux"

        with patch.object(launcher, "launch_discovered_app", return_value=(True, None)) as discovered:
            with patch("helpers.app_launcher.subprocess.Popen") as popen:
                success, reason = launcher.launch_any("prismlauncher")

        self.assertTrue(success)
        self.assertIsNone(reason)
        discovered.assert_called_once_with("prismlauncher")
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
