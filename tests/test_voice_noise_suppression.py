import unittest
import numpy as np

from input.voice import Voice


class VoiceNoiseSuppressionTests(unittest.TestCase):
    def test_low_latency_defaults_use_125ms_blocks(self):
        voice = Voice(sample_rate=16000)
        self.assertEqual(voice.block_size, 2000)
        self.assertEqual(voice.endpoint_silence_blocks, 3)

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

    def test_audio_queue_drops_oldest_packet_when_full(self):
        voice = Voice(noise_suppression=False)
        voice.audio_queue = __import__("queue").Queue(maxsize=1)
        voice.audio_queue.put((b"old", False))
        new_audio = b"\x01\x00" * 8
        voice.audio_callback(new_audio, 8, None, None)
        self.assertEqual(voice.audio_queue.get_nowait()[0], new_audio)

    def test_fast_endpoint_waits_for_configured_silence(self):
        voice = Voice(sample_rate=16000, block_size=2000, endpoint_silence_ms=375)
        self.assertFalse(voice._should_fast_finalize("maya status", 2))
        self.assertTrue(voice._should_fast_finalize("maya status", 3))


if __name__ == "__main__":
    unittest.main()
