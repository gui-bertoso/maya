# Maya

[PT-BR](#pt-br) | [EN](#en)

## PT-BR

A Maya e minha assistente virtual local feita em Python.

Nao e um produto pronto. E um projeto funcional, experimental e bem editavel, que roda no desktop, escuta voz, responde, guarda memoria em JSON e automatiza algumas coisas no sistema.

### O que ela faz

- overlay flutuante com `PySide6`
- wake por palma dupla e atalho
- reconhecimento de voz offline com `Vosk`
- fala com `Piper` ou TTS do sistema
- memoria persistente em JSON
- configuracao por `.env`
- respostas em `data/responses.json`
- textos/config leve em `data/app_text.json`
- launcher de apps/sites
- window showcase
- modo dev e modo reflexivo

### Stack

- Python
- PySide6
- Vosk
- Piper TTS
- pyttsx3
- sounddevice
- python-dotenv

### Estrutura

```text
maya/
|- app.py
|- core/
|- helpers/
|- input/
|- output/
|- data/
|- models/
|- scripts/
|- tests/
```

### Como rodar

```bash
python app.py
```

Primeira vez:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe app.py
```

### Dependencias do sistema

Pra audio funcionar direito, voce precisa do PortAudio.

```bash
# Debian/Ubuntu
sudo apt install portaudio19-dev

# Fedora
sudo dnf install portaudio-devel

# Arch
sudo pacman -S portaudio
```

### Config

As variaveis principais sao:

- `LANGUAGE`
- `VOSK_MODEL_PATH`
- `TTS_ENGINE`
- `MICROPHONE_ENABLED`
- `WAKE_RESPONSE_TEXT`
- `STARTUP_GREETING_ENABLED`
- `DAILY_BRIEF_LOCATION`
- `MEMORY_PATH`
- `RESPONSES_PATH`
- `APP_TEXT_PATH`

Arquivos mais faceis de editar manualmente:

- `data/responses.json`
- `data/app_text.json`
- `.env`
- `data/apps.json`

### Modelos locais

- `models/vosk-model-small-pt-0.3`
- `models/vosk-model-small-en-us-0.15`
- `models/piper/pt_BR-faber-medium.onnx`
- `models/piper/en_US-lessac-high.onnx`

### Build Windows

```powershell
.\scripts\build_windows.bat
```

ou

```powershell
.\scripts\build_setup_windows.bat
```

### Autostart

No Linux, a Maya pode subir no login via `~/.config/autostart/maya.desktop`, apontando para `scripts/start_maya.sh`.

### Testes

```bash
python -m unittest discover -s tests
```

### Exemplos de uso

- `oi`
- `que horas sao`
- `qual a data de hoje`
- `me mostra as noticias de hoje`
- `abrir spotify no chrome`
- `tocar dua lipa no spotify`
- `show open windows`
- `window disco`
- `quero codar`
- `estou pensando demais`

### Dados salvos

- `data/memory.json`
- `data/vocabulary.json`
- `data/responses.json`
- `data/app_text.json`
- `data/apps.json`
- `data/learned_knowledge.json`
- `generated_projects/`

### Limites atuais

- ainda tem bastante heuristica simples
- varias partes ainda sao experimentais
- depende bastante do audio local estar ok
- Wayland limita captura/previews de janela

### Resumo honesto

A Maya e uma assistente local com voz, overlay, memoria em JSON e automacoes de desktop. Ainda nao esta pronta, mas ja esta funcional o bastante pra usar e ir lapidando.

## EN

Maya is my local virtual assistant built in Python.

It is not a polished product. It is a functional, experimental, highly editable desktop project that listens to voice, responds, stores memory in JSON, and automates a few system tasks.

### What it does

- floating overlay with `PySide6`
- wake by double clap and hotkey
- offline speech recognition with `Vosk`
- speech output through `Piper` or system TTS
- persistent JSON memory
- `.env`-based configuration
- responses in `data/responses.json`
- lightweight app text/config in `data/app_text.json`
- app/site launcher
- window showcase
- dev mode and thoughtful mode

### Stack

- Python
- PySide6
- Vosk
- Piper TTS
- pyttsx3
- sounddevice
- python-dotenv

### Structure

```text
maya/
|- app.py
|- core/
|- helpers/
|- input/
|- output/
|- data/
|- models/
|- scripts/
|- tests/
```

### Run

```bash
python app.py
```

First run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe app.py
```

### System dependencies

For audio to work properly, you need PortAudio installed.

```bash
# Debian/Ubuntu
sudo apt install portaudio19-dev

# Fedora
sudo dnf install portaudio-devel

# Arch
sudo pacman -S portaudio
```

### Config

Main variables:

- `LANGUAGE`
- `VOSK_MODEL_PATH`
- `TTS_ENGINE`
- `MICROPHONE_ENABLED`
- `WAKE_RESPONSE_TEXT`
- `STARTUP_GREETING_ENABLED`
- `DAILY_BRIEF_LOCATION`
- `MEMORY_PATH`
- `RESPONSES_PATH`
- `APP_TEXT_PATH`

Best files to edit manually:

- `data/responses.json`
- `data/app_text.json`
- `.env`
- `data/apps.json`

### Local models

- `models/vosk-model-small-pt-0.3`
- `models/vosk-model-small-en-us-0.15`
- `models/piper/pt_BR-faber-medium.onnx`
- `models/piper/en_US-lessac-high.onnx`

### Windows build

```powershell
.\scripts\build_windows.bat
```

or

```powershell
.\scripts\build_setup_windows.bat
```

### Autostart

On Linux, Maya can start on login through `~/.config/autostart/maya.desktop`, pointing to `scripts/start_maya.sh`.

### Tests

```bash
python -m unittest discover -s tests
```

### Usage examples

- `hi`
- `what time is it`
- `what is today's date`
- `show me today's headlines`
- `open spotify on chrome`
- `play dua lipa on spotify`
- `show open windows`
- `window disco`
- `i want to code`
- `i'm overthinking`

### Saved data

- `data/memory.json`
- `data/vocabulary.json`
- `data/responses.json`
- `data/app_text.json`
- `data/apps.json`
- `data/learned_knowledge.json`
- `generated_projects/`

### Current limits

- still uses a lot of simple heuristics
- several parts are still experimental
- depends heavily on local audio working properly
- Wayland limits window capture/previews

### Honest summary

Maya is a local assistant with voice, overlay, JSON memory, and desktop automation. It is not finished, but it is already functional enough to use and keep refining.
