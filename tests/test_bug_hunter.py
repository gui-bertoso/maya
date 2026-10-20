import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from core.input_pipeline import AsyncInputPipeline
from core.knowledge_base import KnowledgeBase
from helpers import backup_manager, config
from helpers.data_expansions import DataExpansionLoader, FORMAT_NAME


def payload(**values):
    return dict(format=FORMAT_NAME, format_version=1, **values)


class BugHunterTests(unittest.TestCase):
    def test_invalid_pack_section_is_isolated_without_alias_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'DataExpansion0.myde').write_text(json.dumps(payload(commands={'thanks':['leaked']},responses=[])))
            (root/'DataExpansion1.myde').write_text(json.dumps(payload(commands={'thanks':['valid']})))
            loader = DataExpansionLoader(root)
            loader.refresh(force=True)
            self.assertEqual(loader.command_aliases, {'thanks':['valid']})
            self.assertEqual(len(loader.errors), 1)

    def test_disappearing_file_preserves_loaded_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'DataExpansion0.myde'
            path.write_text(json.dumps(payload(commands={'thanks':['old']})))
            loader = DataExpansionLoader(directory)
            loader.refresh(force=True)
            with patch.object(loader, '_current_fingerprint', side_effect=FileNotFoundError('race')):
                self.assertFalse(loader.refresh(force=True))
            self.assertEqual(loader.command_aliases, {'thanks':['old']})

    def test_non_utf8_container_is_reported_without_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'DataExpansion0.myde').write_bytes(b'\xff\xfe')
            loader = DataExpansionLoader(directory)
            loader.refresh(force=True)
            self.assertEqual(len(loader.errors),1)

    def test_case_insensitive_container_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'dataexpansion0.MYDE').write_text(json.dumps(payload()))
            loader=DataExpansionLoader(directory)
            loader.refresh(force=True)
            self.assertEqual(loader.loaded_files,['dataexpansion0.MYDE'])

    def test_cancelled_commands_release_pending_count(self):
        running, release = threading.Event(), threading.Event()
        pipeline = AsyncInputPipeline(workers=3, capacity=3)
        pipeline.submit(lambda: (running.set(), release.wait(2)))
        self.assertTrue(running.wait(1))
        pipeline.submit(lambda: None)
        pipeline.submit(lambda: None)
        pipeline.shutdown()
        release.set()
        pipeline._executor.shutdown(wait=True)
        self.assertFalse(pipeline.is_busy)
        self.assertEqual(pipeline._pending,0)

    def test_commands_execute_in_submission_order(self):
        pipeline = AsyncInputPipeline(workers=4, capacity=32)
        order=[]
        for value in range(30): pipeline.submit(order.append,value)
        pipeline._executor.shutdown(wait=True)
        self.assertEqual(order,list(range(30)))

    def test_invalid_last_setting_does_not_partially_write_earlier_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env'
            original='LANGUAGE=en\nTTS_ENGINE=kokoro\nCUSTOM_KEY=keep\n'
            path.write_text(original)
            with patch.object(config,'ENV_FILE',path):
                with self.assertRaises(ValueError):
                    config.save_env_values({'LANGUAGE':'pt-BR','INITIAL_SCALE':'bad'})
            self.assertEqual(path.read_text(),original)

    def test_nonfinite_and_invalid_range_settings_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env'
            with patch.object(config,'ENV_FILE',path):
                for key,value in [('WAKE_DURATION','nan'),('WAKE_DURATION','inf'),('TTS_VOLUME','2'),('INITIAL_MONITOR','0')]:
                    with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                        config.save_env_values({key:value})
            self.assertFalse(path.exists())

    def test_atomic_settings_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env'
            path.write_text('LANGUAGE=en\nCUSTOM_KEY=keep\n')
            original=path.read_bytes()
            with patch.object(config,'ENV_FILE',path),patch.object(config,'set_key',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):config.save_env_values({'WAKE_DURATION':'12'})
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()),['.env'])

    def test_valid_settings_preserve_other_keys_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env'
            path.write_text('LANGUAGE=en\nCUSTOM_KEY=keep\n')
            with patch.object(config,'ENV_FILE',path),patch.object(config,'reload_env') as reload:
                config.save_env_values({'WAKE_DURATION':'12'})
            self.assertIn('CUSTOM_KEY=keep',path.read_text())
            self.assertEqual(config.dotenv_values(path)['WAKE_DURATION'],'12')
            reload.assert_called_once()

    def test_memory_write_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'memory.json'
            path.write_text('{"old": true}')
            original=path.read_bytes()
            with patch.object(backup_manager.json,'dump',side_effect=OSError('full')):
                with self.assertRaises(OSError):backup_manager.safe_json_dump(path,{'new':True})
            self.assertEqual(path.read_bytes(),original)

    def test_rapid_backups_have_distinct_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            path=root/'memory.json';path.write_text('{}')
            with patch.object(backup_manager,'BACKUPS_DIR',root/'backups'):
                one=backup_manager.create_backup(path)
                two=backup_manager.create_backup(path)
            self.assertNotEqual(one,two)
            self.assertTrue(one.exists() and two.exists())

    def test_corrupt_encoding_uses_default_and_retains_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'memory.json';path.write_bytes(b'\xff')
            with patch.object(backup_manager,'BACKUPS_DIR',root/'backups'):
                self.assertEqual(backup_manager.safe_json_load(path,{}),{})
            self.assertEqual(len(list((root/'backups').iterdir())),1)

    def test_malformed_personal_records_are_not_executed_or_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'knowledge.json'
            path.write_text(json.dumps({'records':{'broken':123},'skills':{'bad':{'command':None}}}))
            original=path.read_bytes()
            kb=KnowledgeBase(path)
            self.assertIsNone(kb.get_record('broken'))
            self.assertIsNone(kb.get_skill('bad'))
            self.assertEqual(path.read_bytes(),original)


if __name__=='__main__':unittest.main()
