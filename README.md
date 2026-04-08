# Maya

Maya is a Python virtual assistant with a floating transparent interface, double-clap activation, offline speech recognition through Vosk, voice output through `pyttsx3`, and persistent JSON-based memory.

## What The Project Does

- Listens to the environment for clap detection.
- Wakes up after two consecutive claps.
- Captures speech from the microphone.
- Transcribes speech locally with Vosk.
- Responds using text-to-speech.
- Stores short-term and long-term memory in `data/memory.json`.
- Stores learned vocabulary in `data/vocabulary.json`.
- Displays a real-time floating overlay interface with `PySide6`.
- Can open a faux-3D window showcase carousel for your currently open X11 windows. On Hyprland it can also browse/focus native Wayland clients through `hyprctl`, and on KDE Plasma Wayland it can browse/focus windows through KWin DBus.

## Current Status

At the moment, the project works as an experimental prototype. It already has a full input, processing, and output flow, but the conversation layer is still simple.

Right now Maya can:

- say who she is;
- answer where she is from, how old she is, and which languages she handles best;
- respond to simple greetings;
- react to apologies, compliments, and light insults;
- remember the user's name when they say something like `my name is Guilherme`;
- answer whether she remembers the saved name;
- respond to simple status questions, farewells, and thanks;
- tell the current local time and date;
- store simple preferences such as `i like coffee`;
- store simple facts such as `remember that i work from home`;
- recall saved preferences and remembered facts;
- use saved preferences and facts to personalize greetings, status answers, and fallback replies.

For inputs outside those patterns, the default response is usually:

`i'm still learning, but i'm here with you.`

## Project Structure

```text
maya/
|- app.py
|- core/
|  |- memory.py
|  |- process.py
|  |- vocabulary_manager.py
|- helpers/
|  |- config.py
|  |- vocabulary.py
|- input/
|  |- clap_detector.py
|  |- voice.py
|- output/
|  |- renderer.py
|  |- speaker.py
|- data/
|  |- apps.json
|  |- learned_knowledge.json
|  |- memory.json
|  |- responses.json
|  |- vocabulary.json
|- models/
|  |- vosk-model-small-en-us-0.15/
```

## Technologies Used

- Python
- Vosk
- SoundDevice
- NumPy
- PySide6
- pyttsx3
- python-xlib
- python-dotenv

## Requirements

- Python 3.10+ recommended
- A microphone configured in the operating system
- Python dependencies installed
- A Vosk model available locally

Dependencies expected by the code:

```bash
pip install -r requirements.txt
```

The window showcase mode works best on X11. On Hyprland, Maya can enumerate and focus windows through `hyprctl`, and on KDE Plasma Wayland it can do the same through KWin DBus, but live previews may still be limited because Wayland blocks arbitrary window capture. On other Wayland compositors, including COSMIC, the showcase may be unavailable until a compositor-specific control interface is added.

`sounddevice` also requires the native PortAudio library from the operating system. If PortAudio is missing, Maya will still start after the current fallback handling, but microphone-based clap detection and speech input will stay unavailable until the library is installed.

Common install commands:

```bash
# Debian/Ubuntu
sudo apt install portaudio19-dev

# Fedora
sudo dnf install portaudio-devel

# Arch
sudo pacman -S portaudio
```

## Configuration

The project uses a `.env` file in the root directory. Example based on the current configuration:

```env
VOSK_MODEL_PATH=models/vosk-model-small-en-us-0.15
VOICE_SAMPLE_RATE=16000

TTS_RATE=180
TTS_VOLUME=1.0
TTS_VOICE_ID=

CLAP_THRESHOLD=150
CLAP_COOLDOWN=0.18
CLAP_WINDOW=0.75

WAKE_DURATION=6.0
WAKE_RESPONSE_TEXT=yes?
WAKE_RESPONSE_OPTIONS=oi|fala|to aqui|diz ai|pronto
STARTUP_GREETING_ENABLED=true
STARTUP_GREETING_DELAY=8.0
STARTUP_BRIEF_RESPONSE_WINDOW=20.0
DAILY_BRIEF_LOCATION=

DEBUG_MODE=false
UI_MODE=maya
LANGUAGE=en

WINDOW_WIDTH=260
WINDOW_HEIGHT=260
WINDOW_CAPTION=maya
WINDOW_VSYNC=true
WINDOW_MARGIN=32
WINDOW_TRANSPARENT=true
WINDOW_ALWAYS_ON_TOP=true
QUICK_INPUT_WIDTH=420
QUICK_INPUT_HEIGHT=92

UI_RING_OFFSET_Y=30
UI_RING_RADIUS=105
UI_RING_THICKNESS=24
UI_RING_POINTS=100
UI_STATUS_LABEL_Y=120
UI_HEARD_LABEL_Y=90
UI_RESPONSE_LABEL_Y=60
UI_INPUT_LABEL_Y=28
UI_STATUS_FONT_SIZE=12
UI_HEARD_FONT_SIZE=10
UI_RESPONSE_FONT_SIZE=11
UI_INPUT_FONT_SIZE=12

VOCAB_PATH=data/vocabulary.json
MEMORY_PATH=data/memory.json
RESPONSES_PATH=data/responses.json
APPS_PATH=data/apps.json
KNOWLEDGE_PATH=data/learned_knowledge.json
DEV_PROJECTS_PATH=generated_projects
```

### Main Variables

- `VOSK_MODEL_PATH`: path to the speech recognition model.
- `VOICE_SAMPLE_RATE`: microphone sample rate.
- `TTS_RATE`: speech rate used by text-to-speech.
- `TTS_VOLUME`: speech output volume.
- `TTS_VOICE_ID`: optional voice identifier for the local TTS engine.
- `CLAP_THRESHOLD`: clap detection sensitivity.
- `CLAP_COOLDOWN`: minimum interval between detected claps.
- `CLAP_WINDOW`: time window used to treat two claps as a wake command.
- `WAKE_DURATION`: how long Maya stays awake after activation or user input.
- `WAKE_RESPONSE_TEXT`: short text shown and spoken when Maya wakes up.
- `WAKE_RESPONSE_OPTIONS`: optional `|`-separated list of wake phrases; when set, Maya picks one at random.
- `STARTUP_GREETING_ENABLED`: whether Maya greets you automatically after startup/login.
- `STARTUP_GREETING_DELAY`: delay before the login greeting starts.
- `STARTUP_BRIEF_RESPONSE_WINDOW`: how long Maya listens for your answer after the login greeting.
- `DAILY_BRIEF_LOCATION`: optional location used for the startup weather summary.
- `DEBUG_MODE`: enables terminal logs.
- `WINDOW_WIDTH` and `WINDOW_HEIGHT`: main window size.
- `WINDOW_CAPTION`: title shown in the application window.
- `WINDOW_VSYNC`: enables or disables vertical sync.
- `WINDOW_MARGIN`: distance from screen edges used when Maya moves around the monitor.
- `WINDOW_TRANSPARENT`: enables the transparent floating overlay window mode.
- `WINDOW_ALWAYS_ON_TOP`: keeps the overlay floating above normal windows.
- `QUICK_INPUT_WIDTH` and `QUICK_INPUT_HEIGHT`: size of the separate quick input window opened by the hotkey.
- `VOCAB_PATH`: vocabulary JSON file.
- `MEMORY_PATH`: persistent memory JSON file.
- `RESPONSES_PATH`: response template catalog used for reply variation.
- `APPS_PATH`: app launcher catalog with allowed apps and aliases.
- `KNOWLEDGE_PATH`: learned answers saved by Maya during teaching.
- `DEV_PROJECTS_PATH`: base folder where Maya creates scaffolded development projects.

### App Launcher Notes

The app launcher supports:

- `{username}` placeholders inside app paths, automatically replaced with the current Windows username;
- wildcard patterns such as `*` in versioned folders, so paths like `PyCharm*` or `app-*` keep working after updates.

Examples:

```json
{
  "pycharm": {
    "display_name": "PyCharm",
    "aliases": ["pycharm"],
    "command": "C:\\Program Files\\JetBrains\\PyCharm*\\bin\\pycharm64.exe"
  },
  "vscode": {
    "display_name": "VS Code",
    "aliases": ["vscode", "vs code"],
    "command": "C:\\Users\\{username}\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"
  }
}
```

## How To Run

```bash
python app.py
```

If you are launching Maya from a Flatpak app such as PyCharm, prefer the host-aware launcher below so audio and GTK modules come from the real system instead of the sandbox runtime:

```bash
./run_maya.sh
```

## How To Run Tests

```bash
python -m unittest discover -s tests
```

## How To Use

1. Run the project.
2. Wait for the interface to open.
3. Clap twice to wake Maya.
4. Speak a short command or sentence in English.
5. Maya will transcribe, process, and answer out loud.

You can also press `Ctrl+M` to wake Maya and open a separate quick input window for typing.

Examples of window showcase commands:

- `show open windows`
- `window disco`
- `rotate the window showcase to the right`
- `gira o carrossel de janelas para a esquerda`
- `fechar carrossel de janelas`

Examples of phrases that match the current behavior:

- `who are you`
- `how old are you`
- `where are you from`
- `what language do you speak`
- `hello`
- `good job`
- `sorry`
- `what time is it`
- `what is today's date`
- `my name is Guilherme`
- `do you remember me`
- `remember my name`
- `how are you`
- `what can you do`
- `i like coffee`
- `what do i like`
- `remember that i work from home`
- `what do you remember`
- `start a python project in vscode called weather bot and do an initial commit`
- `create a node project called chat app`
- `create a react app named portfolio and open it in vscode`
- `bye maya`
- `move to top right on monitor 2`

## Memory And Data

- `data/memory.json`: stores recent messages, the user's name, preferences, facts, and state.
- `data/apps.json`: stores the allowlisted apps Maya is allowed to launch.
- `data/learned_knowledge.json`: stores answers Maya learns when you teach her how to respond.
- `data/responses.json`: stores response templates used to vary Maya's replies.
- `data/vocabulary.json`: stores words seen by the system and their generated vectors.
- `generated_projects/`: default location for locally scaffolded development projects.

## Current Limitations

- Conversational pattern recognition is still basic.
- Most responses were designed for English inputs.
- The project depends on properly working local audio input and output.
