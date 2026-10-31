import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.memory import Memory
from core.process import Process
from helpers.self_knowledge import inspect_source, snapshot, reply


class SelfKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.process = Process()
        self.process.memory = Memory()

    def test_inspects_actual_methods_with_line_numbers(self):
        index = inspect_source('core/memory.py')
        self.assertGreater(index['Memory']['save'], 1)
        self.assertIn('load', index['Memory'])

    def test_refuses_nonallowlisted_files_and_paths(self):
        for path in ('.env', '../.env', '/etc/passwd', 'data/memory.json'):
            self.assertEqual(inspect_source(path), {})

    def test_distinguishes_source_from_connected_components(self):
        data = snapshot(self.process)
        apps = next(i for i in data['capabilities'] if i['id'] == 'apps')
        self.assertTrue(apps['implemented'])
        self.assertFalse(apps['connected'])
        self.process.app_launcher = Mock()
        apps = next(i for i in snapshot(self.process)['capabilities'] if i['id'] == 'apps')
        self.assertTrue(apps['connected'])
        self.process.app_launcher.launch.assert_not_called()

    def test_voice_availability_is_not_guessed_from_code(self):
        self.process.parent = SimpleNamespace(voice=object(), speaker=object(), microphone_enabled=False, speech_muted=True)
        by_id = {i['id']: i for i in snapshot(self.process)['capabilities']}
        self.assertFalse(by_id['windows']['connected'])
        self.assertFalse(by_id['voice']['connected'])
        self.assertFalse(by_id['speech']['connected'])

    def test_source_unavailable_does_not_claim_implementation(self):
        with patch('helpers.self_knowledge.inspect_source', return_value={}):
            self.assertFalse(any(i['implemented'] for i in snapshot(self.process)['capabilities']))

    def test_self_questions_are_local_without_model_or_web(self):
        with patch('core.local_conversation.runtime', side_effect=AssertionError('no model')), \
             patch.object(self.process, 'auto_learn_answer', side_effect=AssertionError('no web')):
            self.assertIn('executores', self.process.handle_input('quais são seus poderes?'))
            self.assertIn('core/memory.py', self.process.handle_input('onde fica seu código de memória?'))
            self.assertIn('runtime', self.process.handle_input('status do modelo local'))

    def test_snapshot_never_includes_configuration_secrets_or_user_facts(self):
        self.process.memory.add_known_fact('private secret from user')
        with patch.dict(os.environ, {'API_KEY': 'top-secret-value'}):
            data = str(snapshot(self.process))
        self.assertNotIn('top-secret', data)
        self.assertNotIn('private secret', data)

    def test_voice_status_reports_actual_fallback_not_only_selected_engine(self):
        self.process.parent = SimpleNamespace(voice=SimpleNamespace(active_engine='vosk',status='ready'))
        with patch.dict(os.environ, {'STT_ENGINE':'whisper.cpp','STT_FALLBACK_ENABLED':'true'}):
            answer = reply('status da voz', self.process)
        self.assertIn('selecionado: whisper.cpp', answer)
        self.assertIn('motor em uso: vosk', answer)
        self.assertIn('reserva automática: habilitada', answer)

    def test_self_version_is_verified_and_other_software_is_not_hijacked(self):
        from helpers.version import get_version_display
        self.assertIn(get_version_display(),reply('how are your version',self.process))
        self.assertIsNone(reply('what version of Python should I use?',self.process))

    def test_arbitrary_chat_does_not_trigger_inspection_reply(self):
        self.assertIsNone(reply('hoje o céu estava bonito', self.process))


if __name__ == '__main__':
    unittest.main()
