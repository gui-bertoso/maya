import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('maya_setup_test', ROOT / 'setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
from scripts import install_linux as backend


class Reporter:
    linux_branch = 'feature/voice'
    def info(self, message): pass
    def detail(self, message): pass


def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as result:
        for name, value in files.items(): result.writestr(name, value)
    return buffer.getvalue()


class LinuxInstallerTests(unittest.TestCase):
    def test_branch_resolves_to_immutable_revision(self):
        revision = 'a' * 40
        responses = [io.BytesIO(json.dumps({'sha': revision}).encode()),
                     io.BytesIO(archive({'maya-' + revision + '/scripts/install_linux.py': '# backend'}))]
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'XDG_DATA_HOME': folder}), \
             patch.object(setup.urllib.request, 'urlopen', side_effect=responses) as fetch:
            result = setup.download_linux_source(Reporter())
            self.assertTrue((result / 'scripts/install_linux.py').is_file())
            self.assertIn('feature%2Fvoice', fetch.call_args_list[0].args[0].full_url)
            self.assertIn(revision + '.zip', fetch.call_args_list[1].args[0])

    def test_archive_cannot_escape_install_directory(self):
        responses = [io.BytesIO(json.dumps({'sha': 'b'*40}).encode()),
                     io.BytesIO(archive({'../../escaped': 'bad'}))]
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'XDG_DATA_HOME': folder}), \
             patch.object(setup.urllib.request, 'urlopen', side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, 'caminho inválido'):
                setup.download_linux_source(Reporter())
            self.assertFalse((Path(folder) / 'escaped').exists())

    def test_old_branch_without_backend_leaves_install_intact(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'XDG_DATA_HOME': folder}):
            existing = Path(folder) / 'existing'
            existing.write_text('keep')
            responses = [io.BytesIO(json.dumps({'sha': 'c'*40}).encode()),
                         io.BytesIO(archive({'maya-c/app.py': '# old'}))]
            with patch.object(setup.urllib.request, 'urlopen', side_effect=responses):
                with self.assertRaisesRegex(RuntimeError, 'ainda não contém'):
                    setup.download_linux_source(Reporter())
            self.assertEqual(existing.read_text(), 'keep')
            self.assertFalse((Path(folder) / 'maya/versions' / ('c'*40)).exists())

    def test_personal_data_migration_keeps_old_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = Path(folder) / 'old', Path(folder) / 'new'
            (old / 'data').mkdir(parents=True)
            new.mkdir()
            (old / '.env').write_text('LANGUAGE=pt-BR\n')
            (old / 'data/memory.json').write_text('{"user_name":"guh"}')
            (old / 'models').mkdir()
            with patch.object(backend, 'ROOT', new):
                backend.migrate_state({'path': str(old)})
            self.assertEqual((new / '.env').read_text(), (old / '.env').read_text())
            self.assertEqual((new / 'data/memory.json').read_text(), (old / 'data/memory.json').read_text())
            self.assertEqual((new / 'models').resolve(), old / 'models')

    def test_shortcut_handles_spaces_and_preserves_previous_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'maya with spaces'
            root.mkdir()
            home = Path(folder) / 'home'
            data = home / 'data'
            previous = home / '.local/bin/maya'
            previous.parent.mkdir(parents=True)
            previous.write_text('# old launcher\n')
            with patch.object(backend, 'ROOT', root), patch.object(Path, 'home', return_value=home), \
                 patch.dict('os.environ', {'XDG_DATA_HOME': str(data)}):
                backend.shortcuts()
            self.assertEqual(previous.with_name('maya.maya-backup').read_text(), '# old launcher\n')
            entry = (data / 'applications/maya.desktop').read_text()
            self.assertIn('Exec=/bin/bash "', entry)
            self.assertIn('maya with spaces/scripts/start_maya.sh"', entry)

    def test_voice_archive_rejects_path_traversal(self):
        payload = archive({'../escape': 'bad'})
        with tempfile.TemporaryDirectory() as folder, patch.object(backend, 'ROOT', Path(folder)), \
             patch.object(backend, 'urlopen', return_value=io.BytesIO(payload)):
            with self.assertRaisesRegex(RuntimeError, 'estrutura inesperada'):
                backend.download_vosk(Reporter())


if __name__ == '__main__':
    unittest.main()
