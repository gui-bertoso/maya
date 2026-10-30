# Maya

A local-first personal desktop assistant written in Python. Maya supports natural
English and Portuguese commands, desktop automation, routines, a floating interface
and spoken responses. This branch supports Linux and Windows, including a graphical Linux installer.

> Functional and experimental. Current priorities are low latency, local privacy
> and incremental improvements backed by tests.

## Highlights

- Offline Vosk recognition with the `Maya` / `Maia` wake words.
- Adaptive noise suppression and fast speech endpoint detection.
- Asynchronous processing with bounded queues and semaphores.
- Prewarmed Windows TTS, with optional Piper and Edge engines.
- A/B routines, late-start rescheduling, reminders, XP and streaks.
- PySide6 overlay, quick input, notifications and settings.
- Locally persisted memory, vocabulary and responses.
- Application, web, Spotify and workspace automation.
- Graphical installer and automatic startup.

## Graphical Linux installation

Download **Maya-Setup-x86_64.AppImage** from the [releases](https://github.com/gui-bertoso/maya/releases).
Allow execution in the file properties and open it with a double-click. The x86_64
package includes Python and the setup interface; Maya and speech models are
downloaded during installation.

The setup keeps its runtime in `~/.local/share/maya/setup-runtimes/`, or
`$XDG_DATA_HOME/maya/setup-runtimes/`. The installation keeps working after the
AppImage is closed, moved or removed. On a desktop, `--self-test` opens the
interface and checks a fresh Python environment, headers and HTTPS certificates.

Build with Python 3.12 or later:

```bash
python3 scripts/build_setup_appimage.py
```

The builder downloads pinned Python standalone and AppImage tools, verifies SHA256
and writes the AppImage, checksum and manifest under `dist/`. Speech models and
personal data are not bundled.

Alternatively, download `setup.sh` from `IA_Improvementes` and run:

```bash
bash setup.sh
```

The window lets you select a GitHub branch, download offline speech and open Maya.
The bootstrap stays small: code, dependencies, a compatible Python runtime if
needed, and models are fetched during installation. Unauthenticated installation
and updates require a public repository.

On Fedora and Ubuntu/Debian/Mint, the setup prepares missing system components,
including the installer interface, audio libraries and XWayland. Enter your
password only in the Linux authorization window. A desktop with polkit/pkexec and
a graphical authentication agent is required. If authorization is canceled, start
installation again. Other distributions require these components in advance.

Only the system package manager runs with administrator privileges. The installer,
Python environment and Maya run as your user. Already installed packages are not
reinstalled. The hotkey uses `python-xlib` with X11/XWayland; it does not require
`pynput`, `evdev`, a compiler or development headers. Under Wayland, hotkey coverage
depends on which applications use XWayland. Launching from the application menu
remains available.

The setup installs Qt's XCB/XKB and OpenGL/EGL libraries, avoids host Qt plugin
conflicts and checks the interface and audio modules separately. Failure details
include the exit code or native signal and are saved to the version's
`logs/installer.log`. `pip check` validates Python dependencies; subsequent probes
check native libraries and the graphical session.

On Linux x86_64, if importing ONNX Runtime exits with `SIGILL`, the setup tries
version 1.20.1 once, as allowed by Kokoro 0.6.1, then checks dependencies and import
again. Voice `af_heart` is preserved. This does not guarantee compatibility with
every older processor: if the alternative fails, installation stops with a
diagnostic instead of enabling a crashing voice backend. NumPy, ONNX Runtime and
Kokoro dependencies are probed in separate processes.

Linux NumPy is constrained to `>=2.0.2,<2.4`, satisfying Kokoro while avoiding
NumPy 2.4's x86-64-v2 baseline, which can cause `SIGILL` in `_multiarray_umath` on
older processors. Rerunning the installer also repairs existing environments.
See the [NumPy 2.4 release notes](https://numpy.org/doc/stable/release/2.4.0-notes.html#modulate-dispatched-x86-cpu-features).

Versions are installed under `~/.local/share/maya/versions/`. The setup creates an
application-menu shortcut and `~/.local/bin/maya`. Initial recognition uses English
Vosk and Kokoro voice `af_heart`. No conversational model is downloaded or enabled.

For updates, rerun `setup.sh`, choose **Update Maya…** in the tray menu or send
`update maya` / `!update`. The installer remembers the branch. Close Maya from the
tray **before clicking Install**: a new version copies settings and personal data,
reuses models and retains the previous folder. The shortcut changes only after
the new installation is prepared. A branch without Linux support is rejected.

For development, `bash setup.sh --local-source` installs the local checkout without
downloading GitHub source. Existing installations retain their voice settings.

## Windows quick start

Press **Delete + Page Up** to show Maya from anywhere. Starting a second instance
brings the existing window to the front.

Requirements: Python 3.11, Git and a working microphone.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe app.py
```

With `uv`:

```powershell
uv run --python 3.11 --with-requirements requirements-windows.txt python app.py
```

Optional Portuguese neural voices:

```powershell
.\.venv\Scripts\python.exe scripts\download_piper_models.py --model pt
```

## Routine commands

| Command | Action |
|---|---|
| `!today` | Show today's plan |
| `!done <activity>` | Complete an activity and award XP |
| `!skip <activity>` | Skip an activity |
| `!routine a` / `b` | Choose the 06:00 or 14:00 workout routine |
| `!status` | Show progress, XP and streak |
| `!week` | Summarize the week |
| `!awake HH:MM` | Reschedule the day after waking up late |

## Structure

```text
maya/
├── app.py          # composition and lifecycle
├── core/           # processing, memory, routines and concurrency
├── input/          # microphone, Vosk, noise suppression and claps
├── output/         # interface and speech synthesis
├── helpers/        # integrations and utilities
├── data/           # JSON content and local state
├── models/         # local speech models
├── scripts/        # launchers, downloads and builds
├── tests/          # automated tests
└── docs/           # topic-based documentation
```

## Documentation

- [Overview](docs/overview.en.md)
- [Architecture](docs/architecture.md)
- [Voice pipeline](docs/voice-pipeline.md)
- [Personal routines](docs/routines.md)
- [Development and tests](docs/development.md)
- [Error codes](docs/error-codes.md)
- [Commands and examples](docs/commands.md)
- [Data Expansion containers](docs/data-expansions.md)
- [Roadmap](docs/roadmap.md)
- [Additional Portuguese overview](docs/overview.pt-BR.md)

Visual map: [Maya — Architecture, Flows and Roadmap](https://miro.com/app/board/uXjVHr5wgpk=/).

## Tests

```powershell
uv run --python 3.11 --with-requirements requirements-windows.txt python -m unittest discover -s tests -v
```

## Build

```powershell
.\scripts\build_windows.ps1
.\scripts\build_setup_windows.ps1
```

Generated installers, `build/`, `dist/`, logs and caches do not belong in Git.
Build them locally or distribute them as release assets.

## Privacy

Vosk recognition and personal data remain local. Audio is not recorded by default.
Online engines and integrations are optional and require deliberate configuration.

## Current status

The base is usable. Remaining work includes measured latency, audio diagnostics,
robust barge-in, installer signing and clean-machine tests. See the [roadmap](docs/roadmap.md).

## License

The author's code uses the [MIT License](LICENSE). Third-party materials retain their original licenses.
