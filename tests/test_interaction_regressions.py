import datetime
import queue
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app import App
from output.renderer import Renderer


class InteractionRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.renderer = Renderer(queue.Queue(), submit_input_callback=Mock(return_value=True))

    def tearDown(self):
        self.renderer.timer.stop()
        self.renderer.tray_icon.hide()
        for name in ('root', 'quick_input_window', 'response_bubble', 'settings_window',
                     'dev_editor_window', 'window_showcase_window'):
            getattr(self.renderer, name).hide()
        self.qt.processEvents()

    def make_app(self):
        app = App.__new__(App)
        app.maya_awake_until = time.time() - 1
        app.wake_duration = 6
        app.speaker = SimpleNamespace(is_speaking=False, queue=queue.Queue())
        app.input_pipeline = SimpleNamespace(is_busy=False)
        app.renderer = self.renderer
        app.voice_active = True
        app.wake_word_enabled = True
        app.DEBUG_MODE = False
        app.events = queue.Queue()
        app._last_routine_check_minute = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        return app

    def test_xwayland_uses_actual_qt_backend(self):
        self.assertEqual(self.renderer.window_positioning_limited,
                         self.renderer.is_linux and self.qt.platformName().startswith('wayland'))

    def test_reopening_preserves_draft_and_cursor(self):
        r = self.renderer
        r.show_quick_input()
        QTest.keyClicks(r.quick_input_window.entry, 'minha pergunta')
        r.quick_input_window.entry.setCursorPosition(5)
        r.show_quick_input()
        QTest.keyClicks(r.quick_input_window.entry, ' nova')
        self.assertEqual(r.quick_input_window.entry.text(), 'minha nova pergunta')

    def test_close_and_escape_hide_without_erasing_draft(self):
        r = self.renderer
        r.show_quick_input()
        r.quick_input_window.entry.setText('rascunho')
        r.quick_input_window.close_button.click()
        self.assertFalse(r.quick_input_window.isVisible())
        r.show_quick_input()
        QTest.keyClick(r.quick_input_window.entry, Qt.Key_Escape)
        self.assertFalse(r.quick_input_window.isVisible())
        self.assertEqual(r.quick_input_window.entry.text(), 'rascunho')

    def test_escape_closes_when_button_has_focus(self):
        r = self.renderer
        r.show_quick_input()
        r.quick_input_window.settings_button.setFocus()
        QTest.keyClick(r.quick_input_window.settings_button, Qt.Key_Escape)
        self.assertFalse(r.quick_input_window.isVisible())

    def test_stale_sleep_event_does_not_close_draft(self):
        r = self.renderer
        r.show_quick_input()
        r.quick_input_window.entry.setText('unfinished')
        r.events.put(('app_sleep_ui', None))
        r.handle_events()
        self.assertTrue(r.quick_input_window.isVisible())

    def test_settings_success_message_survives_refresh(self):
        r = self.renderer
        r.apply_settings_callback = Mock(return_value=(True, 'settings applied'))
        r.settings_window.apply_changes()
        self.assertEqual(r.settings_window.status_label.text(), 'settings applied')

    def test_standard_error_reaches_text_without_using_speech(self):
        r=self.renderer
        r.show_quick_input()
        r.events.put(('diagnostic_error',{'code':'MAY-0307','message':'Local speech server unavailable','action':'Check the model'}))
        r.handle_events()
        self.assertIn('[MAY-0307]',r.response_text)
        self.assertIn('Check the model',r.quick_input_window.response_label.text())
        self.assertEqual(r.voice_status,'error')

    def test_rejected_submission_preserves_text(self):
        r = self.renderer
        r.submit_input_callback = Mock(return_value=False)
        r.show_quick_input()
        r.quick_input_window.entry.setText('que horas sao')
        r.quick_input_window.send_button.click()
        self.assertEqual(r.quick_input_window.entry.text(), 'que horas sao')
        self.assertTrue(r.quick_input_window.isVisible())

    def test_draft_survives_expired_wake_timeout(self):
        app = self.make_app()
        self.renderer.show_quick_input()
        self.renderer.quick_input_window.entry.setText('ainda digitando')
        app.update_app_state(1 / 60)
        self.assertGreater(app.maya_awake_until, time.time())
        self.assertTrue(app.events.empty())

    def test_sleep_only_emits_once(self):
        app = self.make_app()
        app.update_app_state(1 / 60)
        first_count = app.events.qsize()
        self.assertGreater(first_count, 0)
        app.update_app_state(1 / 60)
        self.assertEqual(app.events.qsize(), first_count)

    def test_speech_and_processing_keep_overlay_awake(self):
        for target, field in [('speaker', 'is_speaking'), ('input_pipeline', 'is_busy')]:
            with self.subTest(target=target):
                app = self.make_app()
                setattr(getattr(app, target), field, True)
                app.update_app_state(1 / 60)
                self.assertGreater(app.maya_awake_until, time.time())
                self.assertTrue(app.events.empty())

    def test_wake_restores_window_even_inside_wake_deadline(self):
        app = self.make_app()
        app.maya_awake_until = time.time() + 60
        app.microphone_enabled = False
        app.wake_maya('hotkey')
        self.assertEqual(app.events.get()[0], 'app_foreground')

    def test_refresh_preserves_monitor_identity_after_reorder(self):
        left, right = object(), object()
        r = self.renderer
        r.screens = [{'handle': left}, {'handle': right}]
        r.current_monitor_index = 1
        with patch.object(r, '_get_screens', return_value=[{'handle': right}, {'handle': left}]):
            r.refresh_screens()
        self.assertEqual(r.current_monitor_index, 0)

    def test_normal_reply_reaches_text_output(self):
        app = self.make_app()
        app.awaiting_startup_brief_response = False
        app._consume_pending_context_action = lambda _text: None
        app._is_settings_command = lambda _text: False
        app._looks_like_daily_brief_request = lambda _text: False
        app._looks_like_thoughtful_suggestion_case = lambda _text: False
        app._looks_like_dev_mode_suggestion_case = lambda _text: False
        app.process = Mock()
        app.process.detect_patterns.return_value = {}
        app.process.handle_input.return_value = 'agora sao dez horas'
        app.memory = Mock()
        app.speaker = Mock()
        self.assertEqual(app.handle_input('que horas sao'), 'agora sao dez horas')
        self.assertIn(('response_text', 'agora sao dez horas'), list(app.events.queue))


if __name__ == '__main__':
    unittest.main()
