import threading
import time
import unittest
from unittest.mock import Mock, patch
from input.failover_voice import FailoverVoice, GuardedVoskVoice


class Engine:
    DEBUG_MODE = False
    def __init__(self, fail=False):
        self.fail = fail
        self.thread = None
        self.is_listening = False
        self.is_loaded = False
        self.stopped = threading.Event()
        self.last_error = 'test failure'
        self.starts = self.stops = 0

    def start_background(self, final, partial, status):
        self.final, self.partial, self.callback = final, partial, status
        self.starts += 1
        if self.fail:
            status('unavailable')
            return False
        self.stopped.clear()
        def run():
            self.is_listening = self.is_loaded = True
            status('ready')
            self.stopped.wait(5)
            self.is_listening = False
            status('idle')
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stops += 1
        self.stopped.set()


class VoiceFailoverTests(unittest.TestCase):
    def wait(self, predicate):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.01)
        self.fail('timed out waiting for engine state')

    def make(self, primary=None, backup=None):
        primary, backup = primary or Engine(), backup or Engine()
        factory = Mock(return_value=backup)
        wrapper = FailoverVoice(primary, factory)
        self.addCleanup(wrapper.stop)
        return wrapper, primary, backup, factory

    def test_success_does_not_load_backup(self):
        wrapper, primary, backup, factory = self.make()
        wrapper.start_background()
        self.wait(lambda: wrapper.status == 'ready')
        self.assertEqual(wrapper.active_engine, 'whisper.cpp')
        factory.assert_not_called()

    def test_startup_failure_switches_and_preserves_callbacks(self):
        wrapper, primary, backup, factory = self.make(primary=Engine(fail=True))
        received, states = [], []
        wrapper.start_background(on_final_text=received.append, on_status_change=states.append)
        self.wait(lambda: wrapper.active_engine == 'vosk' and wrapper.status == 'ready')
        backup.final('hello maya')
        primary.final('stale command')
        self.assertEqual(received, ['hello maya'])
        self.assertNotIn('error', states)
        self.assertGreater(primary.stops, 0)

    def test_runtime_failure_stops_previous_worker_before_backup_starts(self):
        wrapper, primary, backup, factory = self.make()
        wrapper.start_background()
        self.wait(lambda: wrapper.status == 'ready')
        def create():
            self.assertFalse(primary.thread.is_alive())
            return backup
        factory.side_effect = create
        primary.callback('error')
        self.wait(lambda: wrapper.active_engine == 'vosk' and wrapper.status == 'ready')
        self.assertEqual(primary.starts, 1)
        self.assertEqual(backup.starts, 1)

    def test_both_fail_once_without_retry_loop(self):
        wrapper, primary, backup, factory = self.make(Engine(fail=True), Engine(fail=True))
        wrapper.start_background()
        self.wait(lambda: wrapper.status == 'error')
        self.assertEqual(primary.starts, 1)
        self.assertEqual(backup.starts, 1)

    def test_error_immediately_blocks_final_text_from_failed_engine(self):
        wrapper, primary, backup, factory = self.make()
        received = []
        wrapper.start_background(on_final_text=received.append)
        self.wait(lambda: wrapper.status == 'ready')
        primary.callback('error')
        primary.final('stale command after failure')
        self.assertEqual(received, [])

    def test_app_can_construct_the_configured_failover_without_loading_models(self):
        from app import App
        from helpers.config import get_env as real_get_env
        app=App.__new__(App);app.LANGUAGE='en';app.speaker=Mock()
        def setting(key,*args):
            return {'STT_ENGINE':'whisper.cpp','STT_FALLBACK_ENABLED':'true'}.get(key,real_get_env(key,*args))
        with patch('app.get_env',side_effect=setting):
            voice=app._create_voice()
        self.assertIsInstance(voice, FailoverVoice)
        self.assertFalse(voice.primary.is_loaded)
        self.assertEqual(voice.active_engine,'whisper.cpp')

    def test_stop_does_not_trigger_fallback_or_late_text(self):
        wrapper, primary, backup, factory = self.make()
        received = []
        wrapper.start_background(on_final_text=received.append)
        self.wait(lambda: wrapper.status == 'ready')
        wrapper.stop()
        primary.final('late command')
        self.assertEqual(received, [])
        factory.assert_not_called()
        self.assertEqual(wrapper.status, 'idle')

    def test_stop_during_backup_creation_cannot_start_it_later(self):
        primary, backup = Engine(fail=True), Engine()
        entered, release = threading.Event(), threading.Event()
        def factory():
            entered.set()
            release.wait(2)
            return backup
        wrapper = FailoverVoice(primary, factory)
        self.addCleanup(wrapper.stop)
        wrapper.start_background()
        self.assertTrue(entered.wait(1))
        wrapper.stop()
        release.set()
        self.wait(lambda: not wrapper.thread.is_alive())
        self.assertEqual(backup.starts, 0)

    def test_stop_restart_retries_primary(self):
        wrapper, primary, backup, factory = self.make(Engine(fail=True))
        wrapper.start_background()
        self.wait(lambda: wrapper.active_engine == 'vosk' and wrapper.status == 'ready')
        wrapper.stop()
        primary.fail = False
        wrapper.start_background()
        self.wait(lambda: wrapper.active_engine == 'whisper.cpp' and wrapper.status == 'ready')
        self.assertEqual(primary.starts, 2)

    def test_fast_endpoint_delivers_rescored_final_not_provisional_partial(self):
        from input.voice import Voice
        voice = Voice(noise_suppression=False)
        voice.is_loaded = True
        voice.recognizer = Mock()
        voice.recognizer.AcceptWaveform.return_value = False
        voice.recognizer.PartialResult.return_value = '{"partial":"game plug"}'
        voice.recognizer.FinalResult.return_value = '{"text":"game project"}'
        for _ in range(voice.endpoint_silence_blocks):
            voice.audio_queue.put((b'pcm', False))
        received = []
        def final(text):
            received.append(text)
            voice.stop()
        with patch('input.voice.sd.RawInputStream'):
            voice._listen_loop(on_final_text=final)
        self.assertEqual(received, ['game project'])

    def test_backup_does_not_capture_while_maya_speaks(self):
        voice = GuardedVoskVoice(can_capture=lambda: False, model_path='unused')
        with patch('input.voice.Voice.audio_callback') as callback:
            voice.audio_callback(b'pcm', 1, None, None)
        callback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
