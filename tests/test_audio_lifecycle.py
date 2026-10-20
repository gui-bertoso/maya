import queue
import threading
import unittest
from types import SimpleNamespace
from helpers.app_text import load_app_text
from unittest.mock import MagicMock, patch

from app import App
from input.voice import Voice
from input.clap_detector import ClapDetector


class AudioLifecycleTests(unittest.TestCase):
    def test_voice_stop_exits_without_waiting_for_another_audio_packet(self):
        voice = Voice()
        voice.is_loaded = True
        entered = threading.Event()
        stream = MagicMock()
        stream.__enter__.side_effect = lambda: entered.set()
        with patch('input.voice.sd') as device:
            device.RawInputStream.return_value = stream
            voice.thread = threading.Thread(target=voice._listen_loop)
            voice.thread.start()
            try:
                self.assertTrue(entered.wait(1))
                voice.stop()
                voice.thread.join(1)
                self.assertFalse(voice.thread.is_alive())
                self.assertFalse(voice.is_listening)
            finally:
                voice.stop()
                voice.thread.join(1)

    def test_stop_during_model_loading_does_not_reopen_microphone(self):
        voice = Voice()
        def load(_callback):
            voice.stop()
            voice.is_loaded = True
        voice.load_voice = load
        with patch('input.voice.sd') as device:
            voice._listen_loop()
            device.RawInputStream.assert_not_called()

    def test_clap_stop_exits_without_another_packet(self):
        detector = ClapDetector()
        entered = threading.Event()
        stream = MagicMock()
        stream.__enter__.side_effect = lambda: entered.set()
        with patch('input.clap_detector.sd') as device:
            device.RawInputStream.return_value = stream
            detector.thread = threading.Thread(target=detector.process_audio)
            detector.thread.start()
            try:
                self.assertTrue(entered.wait(1))
                detector.stop()
                detector.thread.join(1)
                self.assertFalse(detector.thread.is_alive())
            finally:
                detector.stop()
                detector.thread.join(1)

    def test_stream_failure_never_reports_ready(self):
        voice = Voice()
        voice.is_loaded = True
        statuses = []
        with patch('input.voice.sd') as device:
            device.RawInputStream.side_effect = RuntimeError('device disconnected')
            voice._listen_loop(on_status_change=statuses.append)
        self.assertEqual(statuses, ['error'])
        self.assertFalse(voice.is_listening)

    def test_failed_capture_clears_active_state(self):
        app = App.__new__(App)
        app.voice_active = True
        app.events = queue.Queue()
        app.handle_voice_status('error')
        self.assertFalse(app.voice_active)
        self.assertEqual(app.events.get(), ('voice_status', 'error'))

    def test_clap_queue_is_bounded(self):
        detector = ClapDetector()
        for _ in range(100):
            detector.audio_callback(b'\0\0', 1, None, None)
        self.assertEqual(detector.audio_queue.qsize(), 16)

    def test_short_unknown_question_is_not_discarded_or_silenced(self):
        app = App.__new__(App)
        app.app_text = load_app_text()
        app.process = SimpleNamespace(
            tokenize=lambda text: text.split(),
            detect_patterns=lambda text: {"asks_unknown": True},
        )
        self.assertTrue(app._is_actionable_voice_text("explain gravity"))
        fallback = app._app_text_values("fallback_prefixes")[0] + " tell me more"
        self.assertFalse(app._should_suppress_voice_response("explain gravity", fallback))
        self.assertFalse(app._is_actionable_voice_text("uh"))

    def test_old_capture_status_cannot_disable_replacement(self):
        app = App.__new__(App)
        app.voice = object()
        app.voice_active = True
        app.events = queue.Queue()
        app._handle_voice_status_from(object(), "idle")
        self.assertTrue(app.voice_active)
        self.assertTrue(app.events.empty())


if __name__ == '__main__':
    unittest.main()
