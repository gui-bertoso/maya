"""Linux backend for the graphical bootstrap. Never installs system packages."""
import ctypes.util
import json
import os
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


def run(command, reporter, cwd=ROOT, env=None):
    reporter.detail(shlex.join(map(str, command)))
    with subprocess.Popen(list(map(str, command)), cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors='replace', bufsize=1) as process:
        for line in process.stdout:
            reporter.detail(line.rstrip())
        if process.wait():
            raise RuntimeError('esta etapa falhou; consulte a saída acima e execute novamente.')


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
    preflight(voice)
    previous = previous_install()
    require_closed({ROOT, Path(previous.get('path', str(ROOT)))})
    migrate_state(previous)
    reporter.info('Preparing runtime: instalando as dependências')
    python = ensure_environment(reporter)
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
