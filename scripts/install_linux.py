"""Linux installer; elevate only the system package manager through polkit."""
import ctypes.util
import json
import os
import platform
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VOSK_NAME = 'vosk-model-small-en-us-0.15'
VOSK_URL = f'https://alphacephei.com/vosk/models/{VOSK_NAME}.zip'


def run(command, reporter, cwd=ROOT, env=None, failure_message=None):
    reporter.detail(shlex.join(map(str, command)))
    with subprocess.Popen(list(map(str, command)), cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors='replace', bufsize=1) as process:
        for line in process.stdout:
            reporter.detail(line.rstrip())
        if process.wait():
            raise RuntimeError(failure_message or 'esta etapa falhou; consulte a saída acima e execute novamente.')


def install_system_dependencies(reporter, voice):
    """Install missing packages with desktop authentication, never sudo the app."""
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        return  # Other distributions can still use a preconfigured environment.
    distro = {release.get('ID', ''), *release.get('ID_LIKE', '').split()}
    if distro & {'fedora'}:
        manager, query = shutil.which('dnf'), shutil.which('rpm')
        packages = ['gcc', 'python3-devel', 'kernel-headers', 'portaudio',
                    'xcb-util-cursor', 'xorg-x11-server-Xwayland']
        query_args = ['-q']
    elif distro & {'debian', 'ubuntu', 'linuxmint'}:
        manager, query = shutil.which('apt-get'), shutil.which('dpkg-query')
        packages = ['build-essential', 'python3-dev', 'linux-libc-dev',
                    'libportaudio2', 'libxcb-cursor0', 'xwayland']
        query_args = ['-W', '-f=${Status}']
    else:
        return
    if voice:
        packages.append('espeak-ng')
    if not manager or not query:
        raise RuntimeError('o gerenciador de pacotes do sistema não está disponível neste ambiente.')
    missing = []
    for package in packages:
        result = subprocess.run([query, *query_args, package], capture_output=True, text=True)
        installed = result.returncode == 0
        if 'debian' in distro or distro & {'ubuntu', 'linuxmint'}:
            installed = installed and result.stdout.strip() == 'install ok installed'
        if not installed:
            missing.append(package)
    if not missing:
        return
    pkexec = shutil.which('pkexec')
    if not pkexec:
        raise RuntimeError('a instalação precisa da autorização do sistema, mas o serviço '
                           'de autorização (polkit/pkexec) não está disponível neste desktop.')
    reporter.info('instalando componentes do sistema; autorize na janela de senha do Linux')
    reporter.detail('componentes necessários: ' + ', '.join(missing))
    run([pkexec, '--disable-internal-agent', manager, 'install', '-y', *missing], reporter,
        failure_message='não foi possível instalar os componentes do sistema. '
        'se a autorização foi cancelada, clique em instalar novamente e autorize na janela do Linux. '
        'caso contrário, confira a conexão e os detalhes acima.')


def preflight(voice):
    if not sys.platform.startswith('linux'):
        raise RuntimeError('este instalador é para Linux.')
    libraries = [('xcb-cursor', 'libxcb-cursor0 (Ubuntu) / xcb-util-cursor (Fedora)'),
                 ('portaudio', 'libportaudio2 (Ubuntu) / portaudio (Fedora)')]
    if voice:
        libraries += [('espeak-ng', 'espeak-ng')]
    missing = [package for library, package in libraries if not ctypes.util.find_library(library)]
    if missing:
        raise RuntimeError('instale estas dependências do sistema e tente novamente: ' + ', '.join(missing))
    if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
        raise RuntimeError('reserve pelo menos 2 GB livres para instalar a maya.')


def download_vosk(reporter):
    models = ROOT / 'models'
    target = models / VOSK_NAME
    if (target / 'am' / 'final.mdl').is_file():
        return
    models.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vosk-', dir=models) as temporary:
        stage = Path(temporary)
        archive_path = stage / 'model.zip'
        reporter.detail('baixando reconhecimento de voz local em inglês (~40 MB).')
        with urlopen(VOSK_URL, timeout=60) as response, archive_path.open('wb') as output:
            received = 0
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > 200 * 1024 ** 2:
                    raise RuntimeError('o download do modelo excedeu o limite esperado.')
                output.write(chunk)
        with zipfile.ZipFile(archive_path) as archive:
            if sum(item.file_size for item in archive.infolist()) > 300 * 1024 ** 2:
                raise RuntimeError('o modelo descompactado excedeu o limite esperado.')
            for item in archive.infolist():
                destination = (stage / item.filename).resolve()
                if not destination.is_relative_to(stage.resolve()) or not item.filename.startswith(VOSK_NAME + '/'):
                    raise RuntimeError('estrutura inesperada no modelo de voz.')
            archive.extractall(stage)
        if not (stage / VOSK_NAME / 'am' / 'final.mdl').is_file():
            raise RuntimeError('download do modelo de voz incompleto.')
        if target.exists():
            raise RuntimeError(f'modelo incompleto em {target}; mova a pasta antes de tentar novamente.')
        shutil.move(stage / VOSK_NAME, target)


def backup_write(path, content, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() != content:
        shutil.copy2(path, path.with_name(path.name + '.maya-backup'))
    path.write_text(content, encoding='utf-8')
    if executable:
        path.chmod(0o755)


def desktop_quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'


def shortcuts():
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    launcher = ROOT / 'scripts/start_maya.sh'
    wrapper = '#!/bin/sh\nexec /bin/bash ' + shlex.quote(str(launcher)) + ' "$@"\n'
    backup_write(Path.home() / '.local/bin/maya', wrapper, executable=True)
    entry = ('[Desktop Entry]\nType=Application\nName=Maya\n'
             'Comment=Assistente pessoal local por voz e texto\n'
             f'Exec=/bin/bash {desktop_quote(launcher)}\n'
             f'Icon={ROOT / "icon.png"}\nPath={ROOT}\n'
             'Terminal=false\nCategories=Utility;\nStartupNotify=false\nStartupWMClass=Maya\n')
    backup_write(data / 'applications/maya.desktop', entry)
    updater = shutil.which('update-desktop-database')
    if updater:
        subprocess.run([updater, str(data / 'applications')], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure_environment(reporter):
    python = ROOT / '.venv/bin/python'
    if python.exists():
        return python
    candidates = [sys.executable, shutil.which('python3.11'), shutil.which('python3.12')]
    for candidate in candidates:
        if not candidate:
            continue
        check = subprocess.run([candidate, '-c',
            'import sys, venv; sys.exit(not ((3,10) <= sys.version_info[:2] <= (3,12)))'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check.returncode == 0:
            run([candidate, '-m', 'venv', ROOT / '.venv'], reporter)
            return python
    reporter.detail('baixando Python 3.11 isolado para compatibilidade com os módulos de voz.')
    bootstrap = ROOT / '.installer'
    run([sys.executable, '-m', 'venv', bootstrap], reporter)
    run([bootstrap / 'bin/python', '-m', 'pip', 'install', 'uv'], reporter)
    uv = bootstrap / 'bin/uv'
    run([uv, 'python', 'install', '3.11'], reporter)
    run([uv, 'venv', '--python', '3.11', '--seed', ROOT / '.venv'], reporter)
    return python


def check_evdev_build(python, reporter):
    """Check native headers against the selected runtime (which may be uv's Python)."""
    compiler = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
    runtime = subprocess.run([str(python), '-c',
        'import json, sys, sysconfig; print(json.dumps(dict('
        'version="%d.%d" % sys.version_info[:2], '
        'includes=[sysconfig.get_path("include"), sysconfig.get_path("platinclude")])))'],
        check=True, capture_output=True, text=True)
    config = json.loads(runtime.stdout)
    if compiler:
        includes = list(dict.fromkeys(path for path in config['includes'] if path))
        probe = subprocess.run(
            [compiler, *['-I' + path for path in includes], '-x', 'c', '-fsyntax-only', '-'],
            input='#include <Python.h>\n#include <linux/input.h>\n#include <linux/input-event-codes.h>\n',
            capture_output=True, text=True)
        if probe.returncode == 0:
            return
        reporter.detail(probe.stderr.strip())
    raise RuntimeError(
        'o evdev (dependência do atalho global) precisa de compilador e headers de desenvolvimento. '
        'não foi possível validar esses componentes após preparar o sistema. '
        f'o Python selecionado é {config["version"]}; se ele foi instalado separadamente, '
        'os headers Python.h precisam corresponder a essa versão. '
        'o Python isolado do uv já inclui seus próprios headers.')


def install_record_path():
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'maya/installation.json'


def previous_install():
    try:
        return json.loads(install_record_path().read_text())
    except (OSError, ValueError):
        return {}


def require_closed(paths):
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            args = (process / 'cmdline').read_bytes().split(b'\0')
            if not any(arg == b'app.py' or arg.endswith(b'/app.py') for arg in args):
                continue
            if (process / 'cwd').resolve() in paths:
                raise RuntimeError('feche a maya pelo menu da bandeja antes de instalar/atualizar. depois abra o instalador novamente.')
        except (OSError, PermissionError):
            continue


def migrate_state(previous):
    old = Path(previous.get('path', str(ROOT)))
    if old == ROOT or not old.is_dir():
        return
    for relative in ('.env', 'data/memory.json', 'data/vocabulary.json',
                     'data/learned_knowledge.json', 'data/routine.json', 'data/backups', 'generated_projects'):
        source, target = old / relative, ROOT / relative
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for relative in ('models', '.runtime'):
        source, target = old / relative, ROOT / relative
        if source.is_dir() and not target.exists():
            target.symlink_to(source.resolve(), target_is_directory=True)


def install(reporter, voice=True, open_app=True, branch='IA_Improvementes', revision=None):
    reporter.info('verificando a instalação Linux')
    previous = previous_install()
    require_closed({ROOT, Path(previous.get('path', str(ROOT)))})
    install_system_dependencies(reporter, voice)
    preflight(voice)
    migrate_state(previous)
    reporter.info('Preparing runtime: instalando as dependências')
    python = ensure_environment(reporter)
    check_evdev_build(python, reporter)
    run([python, '-m', 'pip', 'install', '--upgrade', 'pip'], reporter)
    run([python, '-m', 'pip', 'install', '-r', ROOT / 'requirements.txt'], reporter)
    run([python, '-m', 'pip', 'check'], reporter)
    # A separate process detects missing Qt platform libraries without killing the installer.
    env = os.environ.copy()
    env['QT_QPA_PLATFORM'] = 'xcb' if open_app and env.get('DISPLAY') else 'offscreen'
    run([python, '-c', 'from PySide6.QtWidgets import QApplication; a=QApplication([]); '
         'import sounddevice, vosk, kokoro_onnx; print("interface e módulos carregados")'], reporter, env=env)
    if voice:
        reporter.info('Preparing runtime: baixando os modelos de voz')
        download_vosk(reporter)
        run([python, ROOT / 'scripts/download_kokoro_models.py'], reporter)
        reporter.detail('validando os modelos e gerando uma frase de teste, sem tocar áudio.')
        run([python, ROOT / 'scripts/check_linux_voice.py'], reporter)
    config = ROOT / '.env'
    if not config.exists():
        config.write_text('LANGUAGE=en\nLOCAL_DIALOGUE_ENABLED=false\n'
                          f'MICROPHONE_ENABLED={str(voice).lower()}\nSTT_ENGINE=vosk\n'
                          f'VOSK_MODEL_PATH=models/{VOSK_NAME}\n'
                          'TTS_ENGINE=kokoro\nTTS_VOICE_ID=af_heart\n', encoding='utf-8')
        config.chmod(0o600)
    else:
        reporter.detail('configuração existente preservada; opções de voz se aplicam a instalações novas.')
    reporter.info('Launching: criando o atalho da maya')
    shortcuts()
    record = install_record_path()
    record.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(path=str(ROOT), branch=branch, revision=revision,
                    bootstrap_python=sys.executable)
    backup_write(record, json.dumps(metadata, indent=2) + '\n')
    if open_app:
        if not os.environ.get('DISPLAY'):
            raise RuntimeError('a maya precisa de X11 ou XWayland (DISPLAY) para abrir neste desktop.')
        logdir = ROOT / 'logs'
        logdir.mkdir(exist_ok=True)
        with (logdir / 'session.log').open('a') as log:
            process = subprocess.Popen(['/bin/bash', str(ROOT / 'scripts/start_maya.sh')],
                                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        else:
            if code:
                raise RuntimeError('a maya não abriu; veja logs/session.log para o motivo.')
    reporter.close_success()
