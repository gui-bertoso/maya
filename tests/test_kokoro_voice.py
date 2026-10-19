import queue
import unittest
from unittest.mock import Mock
import numpy as np
from output.speaker import Speaker


class KokoroVoiceTests(unittest.TestCase):
    def make_speaker(self):
        speaker = Speaker.__new__(Speaker)
        speaker.language = 'pt-BR'
        speaker.voice_id = None
        speaker.rate = 180
        speaker.volume = 0.5
        speaker._kokoro_voice = Mock()
        speaker._kokoro_voice.voices = {'pf_dora': object(), 'af_heart': object()}
        speaker._kokoro_voice.create.return_value = (np.array([0.2, -0.4], dtype=np.float32), 24000)
        speaker._play_audio_with_sounddevice = Mock()
        speaker._shift_audio_pitch = Mock(side_effect=AssertionError('Kokoro keeps the natural voice pitch'))
        return speaker

    def test_portuguese_uses_dora_at_original_pitch(self):
        speaker = self.make_speaker()
        self.assertTrue(speaker._speak_with_kokoro('olá'))
        speaker._kokoro_voice.create.assert_called_once_with('olá', voice='pf_dora', lang='pt-br', speed=1.0)
        speaker._shift_audio_pitch.assert_not_called()
        samples, rate = speaker._play_audio_with_sounddevice.call_args.args
        np.testing.assert_allclose(samples, [0.1, -0.2])
        self.assertEqual(rate, 24000)

    def test_english_uses_heart(self):
        speaker = self.make_speaker()
        speaker.language = 'en'
        speaker._speak_with_kokoro('hello')
        speaker._kokoro_voice.create.assert_called_once_with('hello', voice='af_heart', lang='en-us', speed=1.0)

    def test_unknown_voice_reports_error_instead_of_changing_speaker(self):
        speaker = self.make_speaker()
        speaker.voice_id = 'missing'
        with self.assertRaisesRegex(ValueError, 'Unknown Kokoro voice'):
            speaker._speak_with_kokoro('olá')
        speaker._play_audio_with_sounddevice.assert_not_called()

    def test_queue_routes_kokoro_without_using_other_engines(self):
        speaker = self.make_speaker()
        speaker.engine_preference = 'kokoro'
        speaker.queue = queue.Queue()
        speaker.queue.put('olá')
        speaker.queue.put(None)
        speaker.is_running = True
        speaker._prepared_engine = None
        speaker._speak_with_kokoro = Mock(return_value=True)
        speaker._speak_with_piper = Mock()
        speaker._prepare_system_engine = Mock()
        speaker._run()
        speaker._speak_with_kokoro.assert_called_once_with('olá')
        speaker._speak_with_piper.assert_not_called()
        speaker._prepare_system_engine.assert_not_called()
        self.assertFalse(speaker.is_speaking)


if __name__ == '__main__':
    unittest.main()
