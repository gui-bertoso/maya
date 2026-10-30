# Maya

A local-first personal desktop assistant written in Python. Maya supports natural
English and Portuguese commands, desktop automation, routines, a floating interface
and spoken responses. The default branch contains the Windows implementation;
Linux development and its graphical installer are available on
[IA_Improvementes](https://github.com/gui-bertoso/maya/tree/IA_Improvementes).

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

## Windows quick start

Press **End + Page Down** to show Maya from anywhere. Starting a second instance
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
