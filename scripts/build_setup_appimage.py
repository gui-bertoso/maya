"""Build the x86_64 graphical setup from pinned, SHA256-verified upstream assets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    'python.tar.gz': (
        'https://github.com/astral-sh/python-build-standalone/releases/download/20261021/'
        'cpython-3.11.17%2B20261021-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz',
        '224ca8be2d28841e7a382a27c51e74f4ed0aabe249a79294684e782363165948'),
    'appimagetool.AppImage': (
        'https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage',
        'ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0'),
    'runtime-x86_64': (
        'https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64',
        '2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d'),
}


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def fetch_assets(cache):
    cache.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in ASSETS.items():
        target = cache / name
        if target.is_file() and digest(target) == expected:
            continue
        print(f'downloading {name}', flush=True)
        temporary = target.with_suffix('.download')
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Maya-AppImage-Builder'}), timeout=90) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output)
            if digest(temporary) != expected:
                raise RuntimeError(f'invalid checksum: {name}')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def build(work, output):
    if platform.machine() != 'x86_64' or platform.system() != 'Linux':
        raise RuntimeError('this build requires Linux x86_64')
    cache = work / 'downloads'
    fetch_assets(cache)
    appdir = work / 'MayaSetup.AppDir'
    if appdir.exists():
        shutil.rmtree(appdir)
    bundle = appdir / 'usr'
    bundle.mkdir(parents=True)
    with tarfile.open(cache / 'python.tar.gz') as archive:
        archive.extractall(bundle, filter='data')
    for source, target in [(ROOT / 'setup.py', bundle / 'setup.py'),
                           (ROOT / 'icon.png', bundle / 'icon.png'),
                           (ROOT / 'scripts/appimage_launcher.py', bundle / 'launcher.py')]:
        shutil.copy2(source, target)
    identity = hashlib.sha256()
    for path in (bundle / 'setup.py', bundle / 'icon.png', bundle / 'launcher.py'):
        identity.update(path.read_bytes())
    identity.update(ASSETS['python.tar.gz'][1].encode())
    manifest = {'bundle_id': identity.hexdigest(), 'architecture': 'x86_64',
                'python': '3.11.17', 'upstream_assets': ASSETS}
    (bundle / 'bundle.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (appdir / 'AppRun').write_text(
        '#!/bin/sh\nset -eu\n'
        'APPDIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        'unset PYTHONHOME PYTHONPATH\n'
        'exec "$APPDIR/usr/python/bin/python3" -I "$APPDIR/usr/launcher.py" "$@"\n')
    (appdir / 'AppRun').chmod(0o755)
    (appdir / 'maya-setup.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=Maya Setup\n'
        'Comment=Install or update Maya\nExec=AppRun\n'
        'Icon=maya-setup\nTerminal=false\nCategories=Utility;\n')
    shutil.copy2(ROOT / 'icon.png', appdir / 'maya-setup.png')
    (appdir / '.DirIcon').symlink_to('maya-setup.png')
    tool = cache / 'appimagetool.AppImage'
    tool.chmod(0o755)
    extracted = work / 'tool'
    if extracted.exists():
        shutil.rmtree(extracted)
    extracted.mkdir()
    subprocess.run([str(tool), '--appimage-extract'], cwd=extracted, check=True, stdout=subprocess.DEVNULL)
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / 'Maya-Setup-x86_64.AppImage'
    env = dict(os.environ, ARCH='x86_64', SOURCE_DATE_EPOCH='1792713600')
    subprocess.run([str(extracted / 'squashfs-root/AppRun'), '--no-appstream',
                    '--runtime-file', str(cache / 'runtime-x86_64'), str(appdir), str(artifact)],
                   env=env, check=True)
    artifact.chmod(0o755)
    (output / (artifact.name + '.sha256')).write_text(f'{digest(artifact)}  {artifact.name}\n')
    (output / 'Maya-Setup-build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'appimage created: {artifact}', flush=True)
    return artifact


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, default=ROOT / 'build/appimage')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    arguments = parser.parse_args()
    build(arguments.work_dir.resolve(), arguments.output_dir.resolve())
