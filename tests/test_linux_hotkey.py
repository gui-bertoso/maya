import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from helpers.global_hotkey import GlobalHotkeyListener


def keymap(*codes):
    result = [0] * 32
    for code in codes:
        result[code // 8] |= 1 << (code % 8)
    return result


class LinuxHotkeyTests(unittest.TestCase):
    def xlib(self, connection):
        connection.keysym_to_keycode.side_effect = lambda name: {'Delete': 119, 'Prior': 112}[name]
        return SimpleNamespace(XK=SimpleNamespace(string_to_keysym=lambda name: name),
                               display=SimpleNamespace(Display=Mock(return_value=connection)))

    def test_chord_fires_once_after_both_keys_are_released(self):
        listener = GlobalHotkeyListener()
        frames = [keymap(), keymap(119), keymap(119, 112), keymap(119, 112),
                  keymap(112), keymap(), keymap(), keymap(119, 112), keymap()]
        connection = Mock()
        connection.query_keymap.side_effect = frames
        callback = Mock()
        with patch.dict('sys.modules', {'Xlib': self.xlib(connection)}), \
             patch.object(listener._stop_event, 'wait', side_effect=[False] * (len(frames) - 1) + [True]):
            listener._run_linux_hotkey_listener(callback, threading.Event())
        self.assertEqual(callback.call_count, 2)
        connection.close.assert_called_once()
        self.assertFalse(listener.hotkey_registered)

    def test_stopping_listener_terminates_thread_and_closes_connection(self):
        listener = GlobalHotkeyListener()
        connection = Mock()
        connection.query_keymap.return_value = keymap()
        with patch.dict('sys.modules', {'Xlib': self.xlib(connection)}), patch('sys.platform', 'linux'):
            self.assertTrue(listener.start_delete_pgup(Mock()))
            listener.stop()
            listener.thread.join(timeout=1)
            self.assertFalse(listener.thread.is_alive())
        connection.close.assert_called_once()

    def test_unavailable_display_reports_failure_without_hanging(self):
        listener = GlobalHotkeyListener()
        connection = Mock()
        module = self.xlib(connection)
        module.display.Display.side_effect = RuntimeError('display unavailable')
        startup = threading.Event()
        with patch.dict('sys.modules', {'Xlib': module}), patch('helpers.global_hotkey.report_error'):
            listener._run_linux_hotkey_listener(Mock(), startup)
        self.assertTrue(startup.is_set())
        self.assertFalse(listener._startup_success)
        self.assertIn('display unavailable', listener.last_error)

    def test_windows_keeps_existing_listener(self):
        listener = GlobalHotkeyListener()
        callback, startup = Mock(), threading.Event()
        with patch('sys.platform', 'win32'), patch.object(listener, '_run_windows_hotkey_listener') as windows:
            listener._run_delete_pgup_listener(callback, startup)
        windows.assert_called_once_with(callback, startup)


if __name__ == '__main__':
    unittest.main()
