# Development

## Recommended environment

- Python 3.11.
- Windows 10/11 for the default branch.
- `requirements-windows.txt`.
- Vosk models stored in `models/`.

Linux work is maintained on the `IA_Improvementes` branch.

## Tests

```powershell
uv run --python 3.11 --with-requirements requirements-windows.txt python -m unittest discover -s tests -v
```

SQLite tests should run serially to avoid database locks on Windows.

## Organization

- Domain code belongs in `core/`; input/output belongs in `input/` and `output/`.
- Optional integrations belong in `helpers/`.
- New modules should have corresponding tests under `tests/`.
- Keep generated state, caches, logs and binaries out of Git.
- Never commit `.env`, personal data or captured audio.
- User-facing configuration changes should appear in the interface and documentation.

## Windows build

```powershell
.\scripts\build_windows.ps1
.\scripts\build_setup_windows.ps1
```

Publish installers as release assets with a version and checksum. Digital signing
remains planned. Do not commit generated executables.

## Change checklist

1. Preserve JSON compatibility or provide an explicit migration.
2. Run related tests and the full suite.
3. Validate startup, listening and at least one spoken response on the target platform.
4. Run `git diff --check` and exclude local data.
5. Commit small, validated changes before pushing.

Use English Conventional Commit messages, such as `fix: handle a missing microphone`.
