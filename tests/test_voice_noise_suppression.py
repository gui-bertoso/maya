import unittest
import numpy as np

from input.voice import Voice


class VoiceNoiseSuppressionTests(unittest.TestCase):
    def test_quiet_noise_is_gated_to_silence(self):
        voice = Voice(noise_gate=180)
        noise = np.full(4000, 35, dtype=np.int16).tobytes()
        result = np.frombuffer(voice._suppress_noise(noise), dtype=np.int16)
        self.assertTrue(np.all(result == 0))

    def test_voice_level_audio_passes_gate(self):
        voice = Voice(noise_gate=180)
        wave = np.tile(np.array([-1400, 1400], dtype=np.int16), 2000).tobytes()
        result = np.frombuffer(voice._suppress_noise(wave), dtype=np.int16)
        self.assertGreater(np.max(np.abs(result)), 1000)

    def test_hangover_preserves_short_pause(self):
        voice = Voice(noise_gate=180, speech_hangover=2)
        loud = np.tile(np.array([-1400, 1400], dtype=np.int16), 2000).tobytes()
        quiet_phrase_tail = np.tile(np.array([-80, 80], dtype=np.int16), 2000).tobytes()
        voice._suppress_noise(loud)
        result = np.frombuffer(voice._suppress_noise(quiet_phrase_tail), dtype=np.int16)
        self.assertGreater(np.max(np.abs(result)), 0)


if __name__ == "__main__":
    unittest.main()
