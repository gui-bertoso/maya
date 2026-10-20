import json
import queue
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock,patch
from input.whisper_cpp import WhisperServer,WhisperVoice
from app import App


class WhisperBridgeTests(unittest.TestCase):
    def test_transcribe_sends_wav_and_receives_text_over_loopback(self):
        captured=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append((self.path,self.rfile.read(int(self.headers['Content-Length']))))
                body=json.dumps({'text':' Open Spotify. '}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            backend=WhisperServer('unused','unused',prompt='Spotify, Steam')
            backend.url=f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(backend.transcribe(b'\0\0'*1600),'Open Spotify.')
            self.assertEqual(captured[0][0],'/inference')
            self.assertIn(b'RIFF',captured[0][1]);self.assertIn(b'WAVE',captured[0][1])
            self.assertIn(b'Spotify, Steam',captured[0][1])
        finally:server.shutdown();server.server_close();worker.join(1)

    def make_voice(self):
        return WhisperVoice(binary='missing',whisper_model='missing',noise_suppression=False)

    def test_clicks_and_silence_are_not_submitted(self):
        voice=self.make_voice()
        self.assertFalse(voice._queue_segment([b'\0\0'*1600],1))
        self.assertTrue(voice.segments.empty())

    def test_transcription_backlog_is_bounded(self):
        voice=self.make_voice()
        self.assertTrue(voice._queue_segment([b'one'],2))
        self.assertFalse(voice._queue_segment([b'two'],2))
        self.assertEqual(voice.segments.qsize(),1)

    def test_joined_camel_case_wake_word_is_recognized(self):
        app=App.__new__(App);app.wake_words=('maya','maia')
        self.assertEqual(app._extract_wake_word_command('MayaOpen Spotify.'),'open spotify')
        self.assertIsNone(app._extract_wake_word_command('mayapple is a plant'))

    def test_joined_wake_is_removed_even_while_already_awake(self):
        app=App.__new__(App)
        app.wake_words=('maya','maia');app.wake_word_enabled=True
        app.maya_awake_until=time.time()+60;app.wake_duration=12
        app.suppress_wake_final_until=0;app.last_ignored_voice_at=0
        app.ignored_voice_cooldown=0;app.DEBUG_MODE=False
        app.events=queue.Queue();app._is_actionable_voice_text=lambda text:True
        app.submit_input_async=Mock()
        app.handle_voice_input('MayaOpen Spotify.')
        app.submit_input_async.assert_called_once_with('open spotify',input_source='voice')

    def test_wrong_sample_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            WhisperVoice(binary='missing',whisper_model='missing',sample_rate=48000)

    def test_missing_files_report_backend_unavailable(self):
        voice=self.make_voice()
        statuses=[]
        self.assertFalse(voice.start_background(on_status_change=statuses.append))
        self.assertEqual(statuses,['unavailable'])
        self.assertIn('missing',voice.last_error)

    def test_stop_terminates_owned_server(self):
        backend=WhisperServer('unused','unused')
        backend.process=Mock();backend.process.poll.return_value=None
        backend.stop()
        backend.process.terminate.assert_called_once()
        self.assertTrue(backend._stopped.is_set())

    def test_transcription_returns_to_existing_app_callback(self):
        voice=self.make_voice();voice.backend.transcribe=Mock(return_value='Maya open Steam')
        delivered=[]
        def callback(text):delivered.append(text);voice._stop_requested.set()
        voice.segments.put(b'pcm')
        voice._decode_loop(callback,None)
        self.assertEqual(delivered,['Maya open Steam'])

    def test_failed_inference_is_reported(self):
        voice=self.make_voice()
        def fail(*args):voice._stop_requested.set();raise TimeoutError('inference timeout')
        voice.backend.transcribe=fail;voice.segments.put(b'pcm')
        callback=Mock();voice._decode_loop(callback,None)
        callback.assert_not_called();self.assertIn('timeout',voice.last_error)

    def test_settings_choose_whisper_and_preserve_vosk_option(self):
        app=App.__new__(App);app.LANGUAGE='en';app.speaker=Mock()
        from helpers.config import get_env as real_get_env
        with patch('app.get_env',side_effect=lambda key,*args: 'whisper.cpp' if key=='STT_ENGINE' else real_get_env(key,*args)):
            self.assertIsInstance(app._create_voice(),WhisperVoice)
        from input.voice import Voice
        with patch('app.get_env',side_effect=lambda key,*args: 'vosk' if key=='STT_ENGINE' else real_get_env(key,*args)):
            self.assertIs(type(app._create_voice()),Voice)


if __name__=='__main__':unittest.main()
