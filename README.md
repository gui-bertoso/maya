# Maya Linux Setup — English package

English-language rebuild of the graphical Linux x86_64 installer originally
released as `maya-setup-linux-2026.10.23`. This source snapshot preserves that
installer version and translates its interface, progress and error messages.

Download `Maya-Setup-x86_64.AppImage` from the GitHub release, allow execution in
its file properties and open it. Python 3.11 and the graphical interface are
bundled. Maya source and speech models are downloaded during installation.
Choose the GitHub branch in the installer. System packages require authorization
in the Linux password dialog. Public source access is required.

The persistent runtime continues to work after the AppImage is closed, moved or
removed. `--self-test` checks the interface, a fresh Python environment and HTTPS
certificates without installing Maya.

## Build

```bash
python3 scripts/build_setup_appimage.py
```

Pinned upstream SHA256 checksums are verified. The AppImage, `.sha256` file and
`Maya-Setup-build.json` are written to `dist/`. Personal data and speech models
are not bundled. Current development documentation is on
[IA_Improvementes](https://github.com/gui-bertoso/maya/tree/IA_Improvementes).
