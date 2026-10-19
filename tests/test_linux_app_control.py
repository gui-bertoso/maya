import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from helpers.app_launcher import AppLauncher
from helpers.spotify_linux import play_search


class LinuxAppControlTests(unittest.TestCase):
    def test_user_desktop_launcher_overrides_stale_catalog_command(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'applications'
            root.mkdir()
            exe = Path(folder) / 'actual-client'
            exe.write_text('#!/bin/sh\nexit 0\n')
            exe.chmod(0o700)
            (root / 'client.desktop').write_text(f'[Desktop Entry]\nType=Application\nName=GitHub Desktop\nExec="{exe}" --flag %U\n')
            launcher = AppLauncher()
            config = {'display_name': 'GitHub Desktop', 'command_linux': 'missing-command'}
            with patch.object(launcher, '_get_linux_search_roots', return_value=[str(root)]):
                self.assertEqual(launcher._installed_desktop_command(config), [str(exe), '--flag'])

    def test_appimage_launch_and_early_failure_are_handled(self):
        with patch('helpers.app_launcher.subprocess.Popen') as spawn:
            spawn.return_value.wait.return_value = 1
            with self.assertRaises(OSError):
                AppLauncher._spawn(['/apps/Client.AppImage'])
            self.assertEqual(spawn.call_args.args[0], ['/apps/Client.AppImage', '--appimage-extract-and-run'])

    def test_unrelated_playback_is_not_reported_as_requested_track(self):
        def mpris(method, *args):
            if args and args[-1] == 'PlaybackStatus': return "(<'Playing'>,)"
            return "artist: Eminem; title: Without Me"
        with patch('helpers.spotify_linux.evaluate', return_value='Play Eminem'), patch('helpers.spotify_linux.mpris', side_effect=mpris):
            self.assertTrue(play_search('Eminem', 'spotify:search:Eminem'))
        with patch('helpers.spotify_linux.evaluate', return_value='Play Eminem'), patch('helpers.spotify_linux.mpris', side_effect=mpris), patch('helpers.spotify_linux.time.monotonic', side_effect=[0, 0, 20]):
            self.assertFalse(play_search('Radiohead', 'spotify:search:Radiohead'))

if __name__ == '__main__':
    unittest.main()
