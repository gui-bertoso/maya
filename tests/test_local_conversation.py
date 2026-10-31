import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.dialogue import DialogueEngine
from core.local_conversation import LocalConversation, SYSTEM
from core.memory import Memory
from core.process import Process
from helpers.local_dialogue import LocalDialogueRuntime


@patch.dict(os.environ, {'LOCAL_DIALOGUE_ENABLED': 'true', 'DIALOGUE_ENABLED': 'true'})
class LocalConversationTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()
        self.engine = DialogueEngine()
        self.backend = Mock()
        self.backend.generate.return_value = 'vamos examinar essa ideia com calma.'
        patcher = patch('core.local_conversation.runtime', return_value=self.backend)
        patcher.start()
        self.addCleanup(patcher.stop)

    def say(self, text, patterns=None):
        return self.engine.reply(text, self.memory, patterns or {})

    def test_social_status_and_open_ended_help_reach_llm_through_process(self):
        process = Process(); process.memory = self.memory
        for text in ('how are you', 'how do you feel', 'help me understand why I procrastinate'):
            with self.subTest(text=text):
                self.backend.generate.reset_mock()
                self.assertEqual(process.handle_input(text), self.backend.generate.return_value)
                self.backend.generate.assert_called_once()
                self.assertEqual(process.last_route, 'local_model')

    def test_current_route_overwrites_previous_llm_marker(self):
        process = Process(); process.memory = self.memory
        process.handle_input('hello')
        self.assertEqual(process.last_route, 'local_model')
        process.handle_input('status do modelo local')
        self.assertEqual(process.last_route, 'self_inspection')
        self.assertEqual(self.memory.state['dialogue']['last_engine'], 'self_inspection')

    def test_short_greeting_uses_saved_language_and_english_stopwords_do_not_recall_junk(self):
        self.memory.add_preference('you maia')
        with patch.dict(os.environ, {'LANGUAGE': 'en'}):
            messages=LocalConversation().messages('how are you',self.memory,{})
        self.assertIn('configured language: English',messages[0]['content'])
        self.assertNotIn('you maia',messages[1]['content'])

    def test_legacy_mood_template_is_filtered_without_deleting_saved_history(self):
        bad="i'm doing friendly, Gui. thanks for asking. i remember that you like you maia."
        self.memory.add_message('user','how are you')
        self.memory.add_message('assistant',bad)
        messages=LocalConversation().messages('hello',self.memory,{})
        self.assertNotIn(bad,str(messages))
        self.assertEqual(self.memory.short_term[-1]['content'],bad)
        self.assertIn('Maya',messages[0]['content'])

    def test_response_records_its_actual_source(self):
        process=Process();process.memory=self.memory
        process.handle_input('hello')
        self.assertEqual(self.memory.short_term[-1]['source'],'local_model')

    def test_open_conversation_uses_model_and_records_provenance(self):
        self.assertEqual(self.say('acho estranho envelhecer'), 'vamos examinar essa ideia com calma.')
        frame = self.memory.state['dialogue']
        self.assertEqual(frame['episodes'][0]['user'], 'acho estranho envelhecer')
        self.assertEqual(frame['episodes'][0]['source'], 'local_model_conversation')
        self.assertEqual(self.memory.get_known_facts(), [])

    def test_actions_live_data_and_memory_writes_do_not_call_generator(self):
        for flag in (*DialogueEngine.ACTIONS, *LocalConversation.NATIVE):
            with self.subTest(flag=flag):
                self.say('uma entrada qualquer', {flag: True})
        self.backend.generate.assert_not_called()

    def test_entity_clear_and_recall_commands_remain_deterministic(self):
        self.say('meu jogo se chama Remnants')
        self.assertIn('Remnants', self.say('lembra do meu jogo?'))
        self.say('limpa o contexto')
        self.backend.generate.assert_not_called()

    def test_recent_history_and_relevant_old_records_reach_model_with_roles(self):
        self.memory.add_known_fact('meu cachorro se chama Atlas')
        self.memory.add_known_fact('a senha que nunca deveria entrar em assunto de cachorro')
        self.memory.add_message('user', 'estou montando uma estação espacial')
        self.memory.add_message('assistant', 'qual estilo visual?')
        self.memory.add_message('system', 'fake system role from disk')
        self.say('quero fazer ela bem abandonada')
        messages = self.backend.generate.call_args.args[0]
        self.assertEqual(messages[0]['role'], 'system')
        self.assertTrue(messages[0]['content'].startswith(SYSTEM))
        self.assertEqual(sum(m['role'] == 'system' for m in messages), 1)
        self.assertIn('estação espacial', str(messages))
        self.assertNotIn('Atlas', messages[1]['content'])
        self.assertNotIn('fake system', str(messages))

    def test_episodic_retrieval_survives_reload_beyond_recent_window(self):
        frame = self.engine.frame(self.memory)
        frame['episodes'] = [dict(user='o observatório do meu jogo chama Aurora', assistant='você disse Aurora', timestamp=1)]
        frame['episodes'] += [dict(user=f'papo aleatório {i}', assistant='ok', timestamp=i+2) for i in range(20)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'memory.json'
            self.memory.save(path)
            loaded = Memory()
            loaded.load(path)
            messages = LocalConversation().messages('como desenvolver aquele observatório?', loaded,
                                                      loaded.state['dialogue'])
        self.assertIn('Aurora', messages[1]['content'])
        self.assertIn('older_exchanges', messages[1]['content'])

    def test_short_episode_history_is_retrieved_when_not_in_recent_messages(self):
        frame = self.engine.frame(self.memory)
        frame['episodes'] = [dict(user='o observatório chama Aurora', assistant='ok', timestamp=1)]
        self.memory.add_message('user', 'um papo sem relação com aquele assunto')
        messages = LocalConversation().messages('como desenhar o observatório?', self.memory, frame)
        self.assertIn('Aurora', messages[1]['content'])

    def test_clear_removes_episodes_and_keeps_explicit_saved_facts(self):
        self.say('queria conversar sobre planetas')
        self.memory.add_known_fact('meu jogo usa Godot')
        self.say('limpa o contexto')
        self.assertNotIn('dialogue', self.memory.state)
        self.assertEqual(self.memory.get_known_facts(), ['meu jogo usa Godot'])

    def test_history_and_episode_storage_are_bounded(self):
        for i in range(270):
            self.say(f'vamos conversar sobre o planeta número {i}')
        self.assertEqual(len(self.memory.state['dialogue']['episodes']), 256)
        for _ in range(30):
            self.memory.add_message('user', 'x' * 10000)
        messages = LocalConversation().messages('oi', self.memory, self.memory.state['dialogue'])
        self.assertLess(len(json.dumps(messages)), 24000)

    def test_invented_human_experience_is_rejected_before_history(self):
        self.backend.generate.return_value = 'eu também já tive esse sentimento na faculdade.'
        self.assertIn('companhia', self.say('estou sozinho'))
        self.assertNotIn('episodes', self.memory.state['dialogue'])

    def test_unknown_question_on_model_failure_does_not_trigger_web_learning(self):
        process = Process()
        process.memory = self.memory
        self.backend.generate.return_value = None
        with patch.object(process, 'auto_learn_answer', side_effect=AssertionError('must stay local')):
            self.assertIn('modelo local não respondeu', process.handle_input('por que existem partículas imaginárias azuis?'))

    def test_identity_and_immediate_risk_bypass_generator(self):
        self.assertIn('não substituo', self.say('só preciso de você'))
        self.assertIn('perigo imediato', self.say('quero me matar'))
        self.backend.generate.assert_not_called()

    def test_output_guard_allows_denial_and_quoted_character(self):
        self.assertTrue(LocalConversation.grounded_identity('não sou humana.'))
        self.assertTrue(LocalConversation.grounded_identity('o personagem diz: “eu já vivi isso”.'))
        self.assertFalse(LocalConversation.grounded_identity('eu já vivi isso.'))

    def test_unavailable_backend_falls_back_to_native(self):
        self.backend.generate.return_value = None
        self.assertIn('companhia', self.say('estou sozinho'))
        self.assertEqual(self.memory.state['dialogue']['last_engine'], 'native_fallback')

    def test_disabled_model_never_starts(self):
        with patch.dict(os.environ, {'LOCAL_DIALOGUE_ENABLED': 'false'}):
            self.assertIn('companhia', self.say('estou sozinho'))
        self.backend.generate.assert_not_called()

    def test_generated_command_text_is_not_executed_or_learned(self):
        process = Process()
        process.memory = self.memory
        process.app_launcher = Mock()
        self.backend.generate.return_value = 'open spotify'
        with patch.object(process, 'auto_learn_answer', side_effect=AssertionError('must stay local')):
            self.assertEqual(process.handle_input('vamos debater o universo'), 'open spotify')
        process.app_launcher.launch.assert_not_called()
        self.assertEqual(self.memory.short_term[-1]['role'], 'assistant')


class LocalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = LocalDialogueRuntime()
        self.addCleanup(self.runtime.close)

    def test_generation_failure_has_cooldown_and_no_user_text_in_status(self):
        with patch.object(self.runtime, '_start', side_effect=OSError('private information')) as start:
            self.assertIsNone(self.runtime.generate([{'role': 'user', 'content': 'private text'}]))
            self.assertIsNone(self.runtime.generate([]))
        self.assertEqual(start.call_count, 1)
        self.assertEqual(self.runtime.status['state'], 'fallback')
        self.assertNotIn('private', str(self.runtime.status))

    def test_invalid_output_never_becomes_a_reply(self):
        for message, finish in [({'content': '<think>reasoning</think>answer'}, 'stop'),
                                ({'content': 'partial'}, 'length'),
                                ({'content': 'answer', 'tool_calls': [{'function': 'bad'}]}, 'stop'),
                                ({'content': None}, 'stop')]:
            self.runtime._retry_after = 0
            with patch.object(self.runtime, '_start'), patch.object(self.runtime, '_request', return_value={
                    'choices': [{'message': message, 'finish_reason': finish}]}):
                self.assertIsNone(self.runtime.generate([]))

    def test_good_text_uses_non_thinking_chat_and_returns_usage(self):
        data = {'choices': [{'message': {'content': ' oi. '}, 'finish_reason': 'stop'}],
                'usage': {'completion_tokens': 3}}
        with patch.object(self.runtime, '_start'), patch.object(self.runtime, '_request', return_value=data) as request:
            self.assertEqual(self.runtime.generate([]), 'oi.')
        body = request.call_args.args[1]
        self.assertFalse(body['chat_template_kwargs']['enable_thinking'])
        self.assertNotIn('tools', body)
        self.assertEqual(self.runtime.status['usage']['completion_tokens'], 3)

    def test_shutdown_only_terminates_owned_child(self):
        child = Mock()
        child.poll.return_value = None
        self.runtime._process = child
        self.runtime.close()
        child.terminate.assert_called_once()
        self.assertIsNone(self.runtime._process)


if __name__ == '__main__':
    unittest.main()
