import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from core.process import Process
from core.memory import Memory
from core.knowledge_base import KnowledgeBase
from helpers.data_expansions import DataExpansionLoader,FORMAT_NAME


class KnowledgePackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.process=Process()
        self.process.memory=Memory()
        self.process.knowledge_base=KnowledgeBase(self.root/'personal.json')
        self.process.app_launcher=Mock()
        self.process.web_assistant=Mock()

    def tearDown(self):self.temp.cleanup()

    def test_all_hundred_records_are_queryable_without_web_or_execution(self):
        loader=self.process.expansion_loader
        self.assertFalse(loader.errors)
        unique={id(record):record for record in loader.knowledge.values()}
        self.assertEqual(len(unique),100)
        self.assertEqual(len(loader.knowledge),600)
        for question,record in loader.knowledge.items():
            with self.subTest(question=question):
                self.assertEqual(self.process.handle_input(question),record['answer'])
        self.process.web_assistant.research.assert_not_called()
        self.process.app_launcher.launch.assert_not_called()

    def test_explanations_never_become_embedded_actions(self):
        from core.dialogue import DialogueEngine
        for question in ['what is run spotify', 'explain search cats', 'how do i open firefox']:
            with self.subTest(question=question):
                patterns=self.process.detect_patterns(question)
                self.assertFalse(any(patterns.get(key) for key in DialogueEngine.ACTIONS))

    def test_pack_source_is_accessible(self):
        self.process.handle_input('what is python list')
        self.assertIn('docs.python.org',self.process.handle_input('source'))

    def test_user_correction_overrides_pack_without_modifying_pack(self):
        question='what is python list'
        self.process.handle_input('teach: '+question+' => my custom explanation')
        self.assertEqual(self.process.handle_input(question),'my custom explanation')
        self.assertNotEqual(self.process.expansion_loader.get_record(question)['answer'],'my custom explanation')

    def test_pack_cannot_shadow_desktop_action(self):
        path=self.root/'DataExpansion0.myde'
        path.write_text(json.dumps(dict(format=FORMAT_NAME,format_version=1,knowledge=[dict(questions=['open spotify'],answer='hijack',sources=[dict(title='reference',url='https://example.org/')])])) )
        self.process.expansion_loader=DataExpansionLoader(self.root,0)
        self.process.app_launcher.resolve_alias.return_value='spotify'
        self.process.app_launcher.launch.return_value=(True,None)
        self.assertNotEqual(self.process.handle_input('open spotify'),'hijack')
        self.process.app_launcher.launch.assert_called_once_with('spotify')

    def test_pack_knowledge_hot_reload_and_removal(self):
        path=self.root/'DataExpansion0.myde'
        def write(answer):
            path.write_text(json.dumps(dict(format=FORMAT_NAME,format_version=1,knowledge=[dict(questions=['example topic'],answer=answer,sources=[dict(title='ref',url='https://example.org')])])) )
        write('one');loader=DataExpansionLoader(self.root,0)
        self.assertEqual(loader.get_record('example topic')['answer'],'one')
        write('two');self.assertEqual(loader.get_record('example topic')['answer'],'two')
        path.unlink();self.assertIsNone(loader.get_record('example topic'))

    def test_invalid_sources_reject_container(self):
        path=self.root/'DataExpansion0.myde'
        path.write_text(json.dumps(dict(format=FORMAT_NAME,format_version=1,knowledge=[dict(questions=['example'],answer='one',sources=[dict(title='bad',url='javascript:alert(1)')])])) )
        loader=DataExpansionLoader(self.root);loader.refresh(force=True)
        self.assertFalse(loader.knowledge)
        self.assertEqual(len(loader.errors),1)


if __name__=='__main__':unittest.main()
