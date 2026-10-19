import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.dialogue import DialogueEngine
from core.memory import Memory
from core.process import Process


class NativeDialogueTests(unittest.TestCase):
    def setUp(self):
        self.engine = DialogueEngine()
        self.memory = Memory()

    def reply(self,text,patterns=None):
        return self.engine.reply(text,self.memory,patterns or {})

    def test_catalog_has_256_distinct_authored_interactions(self):
        self.assertEqual(len(self.engine.topics),32)
        responses=[r for t in self.engine.topics for r in t['replies'].values()]
        self.assertEqual(len(responses),256)
        self.assertEqual(len(set(responses)),256)
        for topic in self.engine.topics:
            for kind,prefix in [('intro','fale sobre'),('why','por que'),('how','como comecar'),('pitfall','qual o cuidado com'),('challenge','um desafio sobre'),('example','um exemplo de'),('reflection','uma pergunta sobre'),('next','proximo passo em')]:
                with self.subTest(topic=topic['id'],kind=kind):
                    result=self.reply(prefix+' '+topic['title'])
                    self.assertEqual(result,topic['replies'][kind])

    def test_minor_typo_is_chat_retrieval_only(self):
        self.assertEqual(self.reply('me fala de refatoracoa'), self.engine.by_id['refatoracao']['replies']['intro'])
        self.assertIsNone(self.reply('open spootify', {'launch_app': True}))

    def test_ambiguous_topics_request_clarification(self):
        self.assertIn('ou', self.reply('cpu e gpu'))

    def test_contextual_followup_and_topic_change(self):
        self.reply('fale sobre bugs')
        self.assertEqual(self.reply('e por quê?'),self.engine.by_id['bugs']['replies']['why'])
        self.assertEqual(self.reply('me dá um exemplo'),self.engine.by_id['bugs']['replies']['example'])
        self.reply('me fala de git')
        self.assertEqual(self.reply('e por que'),self.engine.by_id['git']['replies']['why'])

    def test_unclear_followup_does_not_invent_topic(self):
        self.assertIn('qual assunto',self.reply('e por que'))
        self.assertIsNone(self.reply('amanha vamos comer uma pizza'))

    def test_actions_are_not_replaced_by_chat(self):
        self.assertIsNone(self.reply('open python',{'launch_app':True}))
        self.assertIsNone(self.reply('move spotify to left',{'move_window':True}))

    def test_explicit_entity_reference_and_saved_recall(self):
        self.assertIn('Remnants',self.reply('meu jogo se chama Remnants'))
        self.reply('ele usa Godot')
        self.assertIn('godot',self.reply('qual engine do meu jogo?'))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'memory.json'
            self.memory.save(path)
            loaded=Memory();loaded.load(path)
            self.assertIn('Remnants',self.engine.reply('lembra do meu jogo?',loaded,{}))

    def test_app_reference_is_bounded_and_not_substituted_in_stories(self):
        self.engine.remember_app(self.memory,'Spotify')
        text,error=self.engine.resolve_action('agora joga ele pra esquerda',self.memory)
        self.assertEqual(text,'mova Spotify para esquerda');self.assertIsNone(error)
        text,error=self.engine.resolve_action('ele parece um aplicativo legal',self.memory)
        self.assertEqual(text,'ele parece um aplicativo legal')
        self.memory.state['app_reference']['used_at']=0
        self.assertIn('qual aplicativo',self.engine.resolve_action('fecha ele',self.memory)[1])

    def test_process_routes_conversation_without_web_or_vocabulary_writes(self):
        process=Process();process.memory=self.memory
        with patch.object(process,'auto_learn_answer',side_effect=AssertionError('web must not run')):
            response=process.handle_input('me fala de bugs')
            self.assertEqual(response,self.engine.by_id['bugs']['replies']['intro'])
            self.assertEqual(process.handle_input('e por que'),self.engine.by_id['bugs']['replies']['why'])

    def test_distinct_named_entities_do_not_overwrite_each_other(self):
        self.reply('meu jogo se chama Remnants')
        self.reply('ele usa Godot')
        self.reply('meu projeto se chama Maya')
        self.assertIn('Remnants', self.reply('qual o nome do meu jogo?'))
        self.assertIn('Maya', self.reply('qual o nome do meu projeto?'))

    def test_observations_can_be_recalled_with_provenance(self):
        self.reply('fale sobre refatoracao')
        self.reply('acho que o problema e o acoplamento')
        self.assertIn('acoplamento', self.reply('lembra do acoplamento?'))

    def test_clear_context_preserves_user_facts(self):
        self.memory.add_known_fact('meu jogo usa Godot')
        self.reply('fale sobre git');self.reply('limpa o contexto')
        self.assertEqual(self.memory.get_known_facts(),['meu jogo usa Godot'])
        self.assertIn('qual assunto',self.reply('e por que'))

if __name__=='__main__':unittest.main()
