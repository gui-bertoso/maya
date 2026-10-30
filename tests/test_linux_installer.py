import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
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
    def test_bootstrap_prepares_gui_without_manual_commands(self):
        for manager, denied in [('dnf', False), ('apt-get', False), ('dnf', True)]:
            with self.subTest(manager=manager, denied=denied), tempfile.TemporaryDirectory() as folder:
                fake = Path(folder)
                programs = {
                    'python3': '#!/bin/sh\nif [ "$1" = "-c" ]; then test -f "$MAYA_TEST_STATE"; '
                               'else printf "%s\\n" "$@" > "$MAYA_TEST_LAUNCH"; fi\n',
                    'pkexec': '#!/bin/sh\nprintf "%s\\n" "$@" > "$MAYA_TEST_AUTH"\n'
                              '[ "$MAYA_TEST_DENY" = 1 ] && exit 126\nshift\nexec "$@"\n',
                    manager: '#!/bin/sh\n: > "$MAYA_TEST_STATE"\n',
                }
                for name, source in programs.items():
                    (fake / name).write_text(source)
                    (fake / name).chmod(0o755)
                (fake / 'dirname').symlink_to(shutil.which('dirname'))
                env = dict(os.environ, PATH=folder, MAYA_TEST_STATE=str(fake / 'ready'),
                           MAYA_TEST_LAUNCH=str(fake / 'launch'), MAYA_TEST_AUTH=str(fake / 'auth'),
                           MAYA_TEST_DENY=str(int(denied)))
                result = subprocess.run(['/bin/bash', str(ROOT / 'setup.sh'), '--local-source'],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, int(denied), result.stderr)
                self.assertEqual((fake / 'launch').exists(), not denied)
                auth = (fake / 'auth').read_text()
                self.assertIn('--disable-internal-agent', auth)
                self.assertIn('python3-tkinter' if manager == 'dnf' else 'python3-tk', auth)
                if not denied:
                    self.assertIn('--local-source', (fake / 'launch').read_text())

    def test_fedora_installs_missing_packages_with_graphical_authorization(self):
        def installed(command, **kwargs):
            return subprocess.CompletedProcess(command, int(command[-1] == 'gcc'), stdout='')
        with patch.object(backend.platform, 'freedesktop_os_release', return_value={'ID': 'fedora'}), \
             patch.object(backend.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name), \
             patch.object(backend.subprocess, 'run', side_effect=installed), \
             patch.object(backend, 'run') as install:
            backend.install_system_dependencies(Reporter(), voice=True)
        self.assertEqual(install.call_args.args[0], [
            '/usr/bin/pkexec', '--disable-internal-agent', '/usr/bin/dnf', 'install', '-y', 'gcc'])

    def test_debian_detects_uninstalled_packages_despite_successful_query(self):
        def installed(command, **kwargs):
            status = 'deinstall ok config-files' if command[-1] == 'linux-libc-dev' else 'install ok installed'
            return subprocess.CompletedProcess(command, 0, stdout=status)
        with patch.object(backend.platform, 'freedesktop_os_release', return_value={'ID': 'linuxmint', 'ID_LIKE': 'ubuntu debian'}), \
             patch.object(backend.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name), \
             patch.object(backend.subprocess, 'run', side_effect=installed), \
             patch.object(backend, 'run') as install:
            backend.install_system_dependencies(Reporter(), voice=False)
        self.assertEqual(install.call_args.args[0], [
            '/usr/bin/pkexec', '--disable-internal-agent', '/usr/bin/apt-get', 'install', '-y', 'linux-libc-dev'])

    def test_existing_system_dependencies_do_not_request_authorization(self):
        with patch.object(backend.platform, 'freedesktop_os_release', return_value={'ID': 'fedora'}), \
             patch.object(backend.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name) as which, \
             patch.object(backend.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='')), \
             patch.object(backend, 'run') as install:
            backend.install_system_dependencies(Reporter(), voice=False)
        install.assert_not_called()
        self.assertNotIn(('pkexec',), [call.args for call in which.call_args_list])

    def test_cancelled_system_install_stops_before_python_and_shortcuts(self):
        with patch.object(backend, 'previous_install', return_value={}), \
             patch.object(backend, 'require_closed'), \
             patch.object(backend, 'install_system_dependencies', side_effect=RuntimeError('autorização cancelada')), \
             patch.object(backend, 'ensure_environment') as environment, \
             patch.object(backend, 'shortcuts') as shortcuts:
            with self.assertRaisesRegex(RuntimeError, 'autorização cancelada'):
                backend.install(Reporter())
        environment.assert_not_called()
        shortcuts.assert_not_called()

    def test_missing_polkit_reports_desktop_authentication_problem(self):
        with patch.object(backend.platform, 'freedesktop_os_release', return_value={'ID': 'fedora'}), \
             patch.object(backend.shutil, 'which', side_effect=lambda name: None if name == 'pkexec' else '/usr/bin/' + name), \
             patch.object(backend.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, stdout='')), \
             patch.object(backend, 'run') as install:
            with self.assertRaisesRegex(RuntimeError, 'polkit/pkexec'):
                backend.install_system_dependencies(Reporter(), voice=False)
        install.assert_not_called()

    def test_evdev_build_checks_headers_of_selected_python(self):
        runtime = subprocess.CompletedProcess([], 0, stdout=json.dumps({
            'version': '3.11', 'includes': ['/isolated/include/python3.11'] }))
        compiled = subprocess.CompletedProcess([], 0, stderr='')
        with patch.object(backend.shutil, 'which', return_value='/usr/bin/cc'), \
             patch.object(backend.subprocess, 'run', side_effect=[runtime, compiled]) as run:
            backend.check_evdev_build(Path('/isolated/bin/python'), Reporter())
        self.assertEqual(run.call_args_list[0].args[0][0], '/isolated/bin/python')
        self.assertIn('-I/isolated/include/python3.11', run.call_args_list[1].args[0])
        self.assertIn('#include <linux/input-event-codes.h>', run.call_args.kwargs['input'])

    def test_evdev_missing_compiler_explains_validation_failure(self):
        runtime = subprocess.CompletedProcess([], 0, stdout=json.dumps({
            'version': '3.11', 'includes': ['/isolated/include/python3.11']}))
        with patch.object(backend.shutil, 'which', return_value=None), \
             patch.object(backend.subprocess, 'run', return_value=runtime) as run:
            with self.assertRaisesRegex(RuntimeError, 'não foi possível validar'):
                backend.check_evdev_build(Path('/isolated/bin/python'), Reporter())
        self.assertEqual(run.call_count, 1)

    def test_evdev_missing_headers_stops_before_dependency_install(self):
        runtime = subprocess.CompletedProcess([], 0, stdout=json.dumps({
            'version': '3.11', 'includes': ['/isolated/include/python3.11']}))
        failed = subprocess.CompletedProcess([], 1, stderr='fatal error: linux/input.h: missing')
        with patch.object(backend.shutil, 'which', return_value='/usr/bin/cc'), \
             patch.object(backend.subprocess, 'run', side_effect=[runtime, failed]), \
             patch.object(backend, 'preflight'), patch.object(backend, 'previous_install', return_value={}), \
             patch.object(backend, 'install_system_dependencies'), \
             patch.object(backend, 'require_closed'), patch.object(backend, 'migrate_state'), \
             patch.object(backend, 'ensure_environment', return_value=Path('/isolated/bin/python')), \
             patch.object(backend, 'run') as install_command:
            with self.assertRaisesRegex(RuntimeError, 'não foi possível validar'):
                backend.install(Reporter(), voice=False, open_app=False)
        install_command.assert_not_called()

    def test_branch_resolves_to_immutable_revision(self):
        revision = 'a' * 40
        responses = [io.BytesIO(json.dumps({'sha': revision}).encode()),
                     io.BytesIO(archive({'maya-' + revision + '/scripts/install_linux.py': '# backend'}))]
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'XDG_DATA_HOME': folder}), \
             patch.object(setup.urllib.request, 'urlopen', side_effect=responses) as fetch:
            reporter = Reporter()
            result = setup.download_linux_source(reporter)
            self.assertEqual(reporter.linux_revision, revision)
            self.assertTrue((result / 'scripts/install_linux.py').is_file())
            self.assertIn('feature%2Fvoice', fetch.call_args_list[0].args[0].full_url)
            self.assertIn(revision + '.zip', fetch.call_args_list[1].args[0])

    def test_archive_cannot_escape_install_directory(self):
        responses = [io.BytesIO(json.dumps({'sha': 'b'*40}).encode()),
                     io.BytesIO(archive({'../../escaped': 'bad'}))]
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'XDG_DATA_HOME': folder}), \
             patch.object(setup.urllib.request, 'urlopen', side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, 'invalid path'):
                setup.download_linux_source(Reporter())
            self.assertFalse((Path(folder) / 'escaped').exists())

    def test_old_branch_without_backend_leaves_install_intact(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'XDG_DATA_HOME': folder}):
            existing = Path(folder) / 'existing'
            existing.write_text('keep')
            responses = [io.BytesIO(json.dumps({'sha': 'c'*40}).encode()),
                         io.BytesIO(archive({'maya-c/app.py': '# old'}))]
            with patch.object(setup.urllib.request, 'urlopen', side_effect=responses):
                with self.assertRaisesRegex(RuntimeError, 'does not contain'):
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

    def test_windows_bundled_installer_does_not_depend_on_linux_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            install = Path(folder) / 'installed'
            payload = Path(folder) / 'Maya.exe'
            payload.write_bytes(b'fixture')
            with patch.object(setup, 'local_install_dir', return_value=install), \
                 patch.object(setup, 'create_windows_shortcuts'), \
                 patch.object(setup, 'is_windows', return_value=False), \
                 patch.object(setup.subprocess, 'Popen'):
                setup.install_bundled_app(payload)
            self.assertEqual((install / 'Maya.exe').read_bytes(), b'fixture')

    def test_update_command_is_explicit_and_does_not_use_learning(self):
        from core.process import Process
        process = Process.__new__(Process)
        process.parent = None
        with patch('helpers.linux_update.open_updater') as updater:
            response = process.handle_input('update maya')
        updater.assert_called_once_with()
        self.assertEqual(process.last_route, 'explicit_update')
        self.assertIn('updater', response.lower())

    def test_voice_archive_rejects_path_traversal(self):
        payload = archive({'../escape': 'bad'})
        with tempfile.TemporaryDirectory() as folder, patch.object(backend, 'ROOT', Path(folder)), \
             patch.object(backend, 'urlopen', return_value=io.BytesIO(payload)):
            with self.assertRaisesRegex(RuntimeError, 'unexpected speech-model structure'):
                backend.download_vosk(Reporter())


if __name__ == '__main__':
    unittest.main()
