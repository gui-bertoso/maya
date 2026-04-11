import sys
import types
import unittest

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.dotenv_values = lambda *args, **kwargs: {}
dotenv_stub.load_dotenv = lambda *args, **kwargs: False
dotenv_stub.set_key = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

pyttsx3_stub = types.ModuleType("pyttsx3")


class _DummyEngine:
    def setProperty(self, *args, **kwargs):
        return None

    def getProperty(self, key):
        if key == "voices":
            return []
        return None

    def say(self, *args, **kwargs):
        return None

    def runAndWait(self):
        return None

    def stop(self):
        return None


pyttsx3_stub.init = lambda *args, **kwargs: _DummyEngine()
sys.modules.setdefault("pyttsx3", pyttsx3_stub)

from output.speaker import Speaker


class SpeakerEngineTests(unittest.TestCase):
    def test_system_preference_disables_piper(self):
        speaker = Speaker(engine_preference="system")
        self.assertFalse(speaker.use_piper)
        self.assertTrue(speaker.use_system_tts)
        speaker.shutdown()

    def test_portuguese_can_use_piper_when_available(self):
        speaker = Speaker(language="pt-BR", engine_preference="piper")
        self.assertTrue(speaker.use_system_tts in (True, False))
        self.assertTrue(speaker.use_piper in (True, False))
        speaker.shutdown()

    def test_piper_preference_keeps_system_fallback_available(self):
        speaker = Speaker(engine_preference="piper")
        self.assertTrue(speaker.use_system_tts in (True, False))
        speaker.shutdown()

    def test_muted_speaker_does_not_queue_text(self):
        speaker = Speaker(muted=True)
        speaker.speak("teste")
        self.assertTrue(speaker.queue.empty())
        speaker.shutdown()


if __name__ == "__main__":
    unittest.main()
