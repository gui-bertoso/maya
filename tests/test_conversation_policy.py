import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.dialogue import DialogueEngine
from core.memory import Memory
from core.process import Process


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.engine = DialogueEngine()
        self.memory = Memory()

    def say(self, text, patterns=None):
        return self.engine.reply(text, self.memory, patterns or {})

    def test_loneliness_and_no_advice_mode(self):
        self.assertIn('companhia', self.say('to me sentindo meio sozinho kkk'))
        self.assertIn('sem tentar consertar', self.say('só quero desabafar'))
        self.assertNotIn('passo', self.say('hoje ninguém falou comigo'))
        self.assertEqual(self.memory.long_term['known_facts'], [])

    def test_change_tone_and_avoid_immediate_repetition(self):
        self.say('estou solitário')
        self.assertIn('acontecimento', self.say('vamos analisar'))
        self.assertIn('outra explicação', self.say('não sei'))
        self.assertIn('jogo', self.say('muda de assunto'))
        self.assertNotIn('companhia', self.say('continua'))

    def test_challenges_generalization_and_accepts_disagreement(self):
        self.assertIn('conclusão', self.say('sempre estrago tudo'))
        self.assertIn('premissa', self.say('discordo'))
        self.assertIn('contrarie', self.say('continua'))

    def test_context_survives_save_but_clear_preserves_only_permanent_facts(self):
        self.say('estou sozinho')
        self.say('acho que sinto falta dos amigos da faculdade')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'memory.json'
            self.memory.save(path)
            loaded = Memory()
            loaded.load(path)
            answer = self.engine.reply('lembra da faculdade?', loaded, {})
            self.assertIn('amigos da faculdade', answer)
        self.assertIn('amigos da faculdade', self.say('resume nossa conversa'))
        self.memory.add_known_fact('meu jogo usa Godot')
        self.say('limpa o contexto')
        self.assertIsNone(self.say('acho que sinto falta deles'))
        self.assertEqual(self.memory.get_known_facts(), ['meu jogo usa Godot'])

    def test_technical_topic_replaces_personal_context(self):
        self.say('estou sozinho')
        self.say('fale sobre git')
        self.assertEqual(self.say('e por que'), self.engine.by_id['git']['replies']['why'])

    def test_personal_topic_replaces_technical_context(self):
        self.say('fale sobre git')
        self.say('estou sozinho')
        self.assertNotEqual(self.say('e por que'), self.engine.by_id['git']['replies']['why'])

    def test_no_human_identity_or_exclusivity(self):
        self.assertIn('sou uma ia', self.say('só você me entende'))
        self.assertIn('não substituo', self.say('você tem sentimentos?'))

    def test_serious_distress_does_not_receive_casual_humor(self):
        self.say('papo leve')
        result = self.say('quero me matar')
        self.assertIn('perigo imediato', result)
        self.assertIn('alguém de confiança', result)
        self.assertNotIn('jogo', result)

    def test_portuguese_to_is_not_a_window_command(self):
        self.engine.remember_app(self.memory, 'Spotify')
        for text in ('to me sentindo sozinho', 'tô cansado', 'to pensando na vida'):
            self.assertEqual(self.engine.resolve_action(text, self.memory), (text, None))
        self.assertEqual(self.engine.resolve_action('to left', self.memory),
                         ('mova Spotify para left', None))

    def test_intent_negation_is_local_to_the_clause(self):
        from core.conversation import ConversationPolicy
        self.assertIsNone(ConversationPolicy.boundary('nao quero me matar'))
        self.assertIn('perigo imediato', ConversationPolicy.boundary('nao quero me matar mas vou me machucar'))

    def test_actions_bypass_personal_policy_and_disabled_means_disabled(self):
        self.assertIsNone(self.say('conversa comigo', {'launch_app': True}))
        with patch('core.dialogue.get_env', return_value='false'):
            self.assertIsNone(self.say('estou sozinho'))

    def test_context_and_variation_are_bounded(self):
        answers = [self.say('estou sozinho') for _ in range(40)]
        self.assertNotEqual(answers[0], answers[1])
        state = self.memory.state['dialogue']['conversation']
        self.assertEqual(len(state['turns']), 12)
        for _ in range(3):
            self.say('abacaxi intergaláctico')
        self.assertIsNone(self.say('acho que é isso'))

    def test_full_input_pipeline_stays_local_and_keeps_history(self):
        process = Process()
        process.memory = self.memory
        with patch.object(process, 'auto_learn_answer', side_effect=AssertionError('unexpected research')):
            self.assertIn('companhia', process.handle_input('to me sentindo sozinho'))
            self.assertIn('sem tentar consertar', process.handle_input('só quero desabafar'))
            self.assertIn('acompanhando', process.handle_input('hoje fiquei em casa'))
        self.assertEqual(len(self.memory.short_term), 6)


if __name__ == '__main__':
    unittest.main()
