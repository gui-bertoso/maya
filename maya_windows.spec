# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


PROJECT_DIR = Path(__file__).resolve().parent


def build_datas():
    datas = []

    for relative_path in ("data", "models", ".env"):
        source_path = PROJECT_DIR / relative_path
        if source_path.exists():
            datas.append((str(source_path), relative_path))

    return datas


hiddenimports = [
    "pyttsx3.drivers.sapi5",
    "sounddevice",
]
hiddenimports += collect_submodules("comtypes")
hiddenimports += collect_submodules("pynput")

datas = build_datas()

block_cipher = None


a = Analysis(
    ["app.py"],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    exclude_binaries=False,
    name="Maya",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
