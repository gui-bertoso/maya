"""Explicit Linux update action; never execute actions inferred from dialogue."""
import json
import os
from pathlib import Path
import subprocess
import sys


def open_updater():
    if not sys.platform.startswith('linux'):
        raise RuntimeError('o atualizador Linux está disponível somente no Linux.')
    root = Path(__file__).resolve().parent.parent
    metadata = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'maya/installation.json'
    try:
        record = json.loads(metadata.read_text())
    except (OSError, ValueError):
        record = {}
    env = os.environ.copy()
    env['MAYA_INSTALL_REF'] = record.get('branch', 'IA_Improvementes')
    # The installer needs the desktop Python with Tk, rather than the app venv.
    logdir = root / 'logs'
    logdir.mkdir(exist_ok=True)
    with (logdir / 'updater.log').open('a') as log:
        process = subprocess.Popen(['/bin/bash', str(root / 'setup.sh')], cwd=root, env=env,
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        result = process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        return
    if result:
        raise RuntimeError('não foi possível abrir o atualizador; consulte logs/updater.log.')
