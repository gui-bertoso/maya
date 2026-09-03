import sys
import types
import unittest
from unittest.mock import patch

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
import output.speaker as speaker_module


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

    def test_edge_preference_works_on_windows_when_dependency_is_available(self):
        with patch.object(speaker_module, "edge_tts", object()), patch.object(speaker_module.sys, "platform", "win32"):
            speaker = Speaker(language="en-US", engine_preference="edge")
            self.assertTrue(speaker.use_edge_tts)
            self.assertFalse(speaker.use_piper)
            speaker.shutdown()

    def test_auto_prefers_edge_for_portuguese_on_windows(self):
        with patch.object(speaker_module, "edge_tts", object()), patch.object(speaker_module.sys, "platform", "win32"):
            speaker = Speaker(language="pt-BR", engine_preference="auto")
            self.assertTrue(speaker.use_edge_tts)
            speaker.shutdown()

    def test_muted_speaker_does_not_queue_text(self):
        speaker = Speaker(muted=True)
        speaker.speak("teste")
        self.assertTrue(speaker.queue.empty())
        speaker.shutdown()

    def test_prepared_system_engine_is_consumed_once(self):
        speaker = Speaker(engine_preference="system")
        prepared = _DummyEngine()
        speaker._prepared_engine = prepared
        self.assertIs(speaker._take_prepared_engine(), prepared)
        self.assertIsNone(speaker._prepared_engine)
        speaker.shutdown()


if __name__ == "__main__":
    unittest.main()
