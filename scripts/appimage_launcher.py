"""Persist the bundled installer/runtime before creating any application venv."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def prepare_runtime(bundle, data_home):
    manifest = json.loads((bundle / 'bundle.json').read_text())
    identity = manifest['bundle_id']
    if len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity):
        raise RuntimeError('invalid bundle identifier')
    parent = data_home / 'maya' / 'setup-runtimes'
    target = parent / identity
    parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix='.setup-', dir=parent) as temporary:
            staged = Path(temporary) / 'runtime'
            shutil.copytree(bundle, staged, symlinks=True)
            try:
                staged.rename(target)
            except OSError:
                if not target.is_dir():
                    raise
    if not (target / 'python/bin/python3').is_file() or not (target / 'setup.py').is_file():
        raise RuntimeError(f'incomplete installer environment in {target}')
    if (target / 'bundle.json').read_bytes() != (bundle / 'bundle.json').read_bytes():
        raise RuntimeError(f'incompatible installer environment in {target}')
    return target


def self_test(target):
    """Exercise the persistent Python, Tk GUI, TLS and a newly created venv."""
    python = target / 'python/bin/python3'
    with tempfile.TemporaryDirectory(prefix='maya-appimage-test-') as folder:
        environment = Path(folder) / 'venv'
        subprocess.run([str(python), '-I', '-m', 'venv', str(environment)], check=True)
        code = (
            'import importlib.util, pathlib, ssl, sys, tkinter; '
            'spec=importlib.util.spec_from_file_location("maya_setup", sys.argv[1]); '
            'setup=importlib.util.module_from_spec(spec); spec.loader.exec_module(setup); '
            'window=setup.SetupWindow(); window.root.update(); window.root.destroy(); '
            'assert pathlib.Path(sys.base_prefix, "include/python3.11/Python.h").is_file(); '
            'assert ssl.create_default_context().get_ca_certs(); '
            'print("MAYA_APPIMAGE_OK: python, interface, venv, headers and TLS")'
        )
        subprocess.run([str(environment / 'bin/python'), '-I', '-c', code, str(target / 'setup.py')], check=True)


def main():
    bundle = Path(__file__).resolve().parent
    data_home = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    target = prepare_runtime(bundle, data_home)
    if sys.argv[1:] == ['--self-test']:
        self_test(target)
        return
    python = target / 'python/bin/python3'
    os.execv(str(python), [str(python), '-I', str(target / 'setup.py'), *sys.argv[1:]])


if __name__ == '__main__':
    main()
