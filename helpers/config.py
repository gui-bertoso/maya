from helpers.diagnostics import report_error
import os
import math
import tempfile
import shutil
import sys
from helpers.dialogue_settings import SETTINGS as DIALOGUE_SETTINGS
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key

PROJECT_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "maya"


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def get_bundle_dir():
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return PROJECT_DIR


def get_runtime_dir():
    if not is_frozen():
        return PROJECT_DIR

    if sys.platform.startswith("win"):
        base_dir = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    else:
        base_dir = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))

    return base_dir / APP_NAME


def get_resource_path(relative_path):
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return get_bundle_dir() / path


def get_runtime_path(relative_path):
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return get_runtime_dir() / path


def _copy_if_missing(source_path, target_path):
    if not source_path.exists() or target_path.exists():
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if source_path.is_dir():
        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
    else:
        shutil.copy2(source_path, target_path)


def ensure_runtime_layout():
    if not is_frozen():
        return

    runtime_env = get_runtime_path(".env")
    if runtime_env.is_dir():
        nested_env = runtime_env / ".env"
        recovered = nested_env.read_bytes() if nested_env.is_file() else b""
        shutil.rmtree(runtime_env)
        if recovered:
            temporary_env = runtime_env.with_suffix(".tmp")
            temporary_env.write_bytes(recovered)
            temporary_env.replace(runtime_env)

    for relative_path in (
        ".env",
        "data/app_text.json",
        "data/apps.json",
        "data/learned_knowledge.json",
        "data/memory.json",
        "data/responses.json",
        "data/routine.json",
        "data/vocabulary.json",
        "data/expansions",
    ):
        _copy_if_missing(
            get_resource_path(relative_path),
            get_runtime_path(relative_path),
        )

    get_runtime_path("data/backups").mkdir(parents=True, exist_ok=True)
    get_runtime_dir().mkdir(parents=True, exist_ok=True)


ENV_FILE = get_runtime_path(".env")


@dataclass(frozen=True)
class EnvField:
    key: str
    default: str
    cast: type = str
    category: str = "General"
    label: str | None = None
    help_text: str = ""
    options: tuple[str, ...] = ()


ENV_FIELDS = (
    EnvField("DEBUG_MODE", "false", str, "General", "Debug Mode", "Enable verbose logs.", ("true", "false")),
    EnvField("UI_MODE", "maya", str, "General", "UI Mode", "Current UI variant name."),
    EnvField("LANGUAGE", "en", str, "General", "Language", "Assistant language code.", ("en", "pt-BR")),
    EnvField("WAKE_DURATION", "6.0", float, "Wake", "Wake Duration", "How long Maya stays awake after interaction."),
    EnvField("WAKE_RESPONSE_COOLDOWN", "2.5", float, "Wake", "Wake Response Cooldown", "Minimum delay between spoken wake responses."),
    EnvField("WAKE_RESPONSE_TEXT", "oi, tô ouvindo.", str, "Wake", "Wake Response Text", "Fallback spoken answer when Maya wakes."),
    EnvField("WAKE_RESPONSE_OPTIONS", "", str, "Wake", "Wake Response Options", "Pipe-separated wake phrases, for example: yes?|what's up?"),
    EnvField("SPEAK_WAKE_RESPONSE", "true", str, "Wake", "Speak Wake Response", "Whether Maya speaks when it wakes up.", ("true", "false")),
    EnvField("SPEAK_WAKE_RESPONSE_ON_CLAP", "true", str, "Wake", "Speak On Clap", "Whether Maya speaks after double clap.", ("true", "false")),
    EnvField("SPEAK_WAKE_RESPONSE_ON_HOTKEY", "true", str, "Wake", "Speak On Hotkey", "Whether Maya speaks after hotkey wake.", ("true", "false")),
    EnvField("WAKE_WORD_ENABLED", "true", str, "Wake", "Wake Word", "Keep listening locally for Maya or Maia.", ("true", "false")),
    EnvField("WAKE_WORDS", "maya|maia", str, "Wake", "Wake Words", "Pipe-separated names that wake Maya."),
    EnvField("SPEAK_WAKE_RESPONSE_ON_WORD", "true", str, "Wake", "Speak On Wake Word", "Whether Maya answers after hearing her name.", ("true", "false")),
    EnvField("STARTUP_GREETING_ENABLED", "true", str, "Wake", "Startup Greeting", "Whether Maya greets you after login/startup.", ("true", "false")),
    EnvField("STARTUP_GREETING_DELAY", "8.0", float, "Wake", "Startup Greeting Delay", "Delay in seconds before the startup greeting."),
    EnvField("STARTUP_BRIEF_RESPONSE_WINDOW", "20.0", float, "Wake", "Startup Brief Response Window", "How long Maya stays awake waiting for your answer to the startup brief."),
    EnvField("DAILY_BRIEF_LOCATION", "", str, "Wake", "Daily Brief Location", "Optional weather location for the startup daily brief."),
    EnvField("VOICE_IGNORE_COOLDOWN", "1.2", float, "Voice", "Voice Ignore Cooldown", "Cooldown for low-signal voice input suppression."),
    EnvField("MICROPHONE_ENABLED", "true", str, "Voice", "Microphone Enabled", "Enable microphone-driven voice recognition and clap wake.", ("true", "false")),
    EnvField("STT_FALLBACK_ENABLED", "false", str, "Voice", "Automatic Vosk fallback", "If Whisper fails, stop it and try the configured Vosk model. Restart recognition to retry Whisper.", ("true", "false")),
    EnvField("STT_ENGINE", "vosk", str, "Voice", "Speech recognition engine", "Vosk streaming or local whisper.cpp sentence transcription.", ("vosk", "whisper.cpp")),
    EnvField("WHISPER_CPP_SERVER", ".runtime/whisper.cpp/build/bin/whisper-server", str, "Voice", "Whisper server binary", "Local compiled whisper-server executable."),
    EnvField("WHISPER_MODEL_PATH", "models/whisper/ggml-small.en.bin", str, "Voice", "Whisper model", "Local ggml model file; small.en is the initial English experiment."),
    EnvField("WHISPER_THREADS", "6", int, "Voice", "Whisper CPU threads", "CPU threads available to the local recognition server."),
    EnvField("WHISPER_USE_GPU", "true", str, "Voice", "Whisper GPU", "Use a supported compiled GPU backend, such as Vulkan.", ("true", "false")),
    EnvField("WHISPER_PROMPT", "Maya, Steam, Spotify, Firefox, Godot, Blender, VS Code.", str, "Voice", "Whisper vocabulary hints", "Short context for proper names; this is a hint, not an accuracy guarantee."),
    EnvField("VOICE_SAMPLE_RATE", "16000", int, "Voice", "Voice Sample Rate", "Recognizer microphone sample rate."),
    EnvField("VOICE_BLOCK_SIZE", "2000", int, "Voice", "Voice Block Size", "Smaller blocks reduce wake word latency."),
    EnvField("VOICE_NOISE_SUPPRESSION", "true", str, "Voice", "Noise Suppression", "Adaptive input noise gate before speech recognition.", ("true", "false")),
    EnvField("VOICE_NOISE_GATE", "180", int, "Voice", "Noise Gate", "Minimum microphone RMS treated as speech."),
    EnvField("VOICE_NOISE_MULTIPLIER", "2.2", float, "Voice", "Noise Multiplier", "Speech must be this many times louder than ambient noise."),
    EnvField("VOICE_SPEECH_HANGOVER", "4", int, "Voice", "Speech Hangover", "How many blocks remain open across short pauses."),
    EnvField("VOICE_FAST_ENDPOINT", "true", str, "Voice", "Fast Voice Response", "Answer from a stable partial result as soon as speech ends.", ("true", "false")),
    EnvField("VOICE_ENDPOINT_SILENCE_MS", "375", int, "Voice", "End Of Speech Delay", "Silence required before Maya answers a recognized phrase."),
    EnvField("VOSK_MODEL_PATH", "models/vosk-model-small-pt-0.3", str, "Voice", "Vosk Model Path", "Relative path to the Vosk speech model."),
    EnvField("CLAP_THRESHOLD", "150", int, "Audio", "Clap Threshold", "Minimum RMS to count as a clap."),
    EnvField("CLAP_COOLDOWN", "0.18", float, "Audio", "Clap Cooldown", "Minimum delay between clap detections."),
    EnvField("CLAP_WINDOW", "0.75", float, "Audio", "Double Clap Window", "Maximum delay between claps for wake."),
    EnvField("TTS_RATE", "180", int, "Speech", "TTS Rate", "Speech rate for pyttsx3."),
    EnvField("TTS_VOLUME", "1.0", float, "Speech", "TTS Volume", "Speech volume from 0.0 to 1.0."),
    EnvField("SPEECH_MUTED", "false", str, "Speech", "Speech Muted", "Mute Maya's spoken voice while keeping text responses visible.", ("true", "false")),
    EnvField("TTS_ENGINE", "auto", str, "Speech", "TTS Engine", "Kokoro provides local neural voices. Auto prefers Edge in pt-BR, then Piper.", ("auto", "kokoro", "edge", "piper", "system")),
    EnvField("TTS_VOICE_ID", "", str, "Speech", "TTS Voice ID", "Voice ID for the selected engine. Kokoro: pf_dora (pt-BR), af_heart (English). Blank selects a default."),
    EnvField("SPOTIFY_UI_CONTROL", "true", str, "Media", "Spotify playback control", "Read Spotify's local interface to play matching search results. Applies when Maya starts Spotify.", ("true", "false")),
    EnvField("SPOTIFY_CONTROL_PORT", "9229", int, "Media", "Spotify local control port", "Local loopback port for Spotify desktop controls. Restart Spotify after changing it."),
    EnvField("WINDOW_WIDTH", "260", int, "Overlay", "Window Width", "Base overlay width."),
    EnvField("WINDOW_HEIGHT", "260", int, "Overlay", "Window Height", "Base overlay height."),
    EnvField("WINDOW_MARGIN", "32", int, "Overlay", "Window Margin", "Distance from screen edges."),
    EnvField("INITIAL_POSITION", "top_right", str, "Overlay", "Initial Position", "Overlay anchor position.", ("top_left", "top", "top_right", "left", "center", "right", "bottom_left", "bottom", "bottom_right")),
    EnvField("INITIAL_MONITOR", "2", int, "Overlay", "Initial Monitor", "1-based monitor number for the overlay."),
    EnvField("INITIAL_SCALE", "0.5", float, "Overlay", "Initial Scale", "Initial overlay scale factor."),
    EnvField("QUICK_INPUT_WIDTH", "420", int, "Overlay", "Quick Input Width", "Quick input popup width."),
    EnvField("QUICK_INPUT_HEIGHT", "160", int, "Overlay", "Quick Input Height", "Quick input command center height."),
    EnvField("QUICK_INPUT_POSITION", "bottom", str, "Overlay", "Input position", "Where the command box opens.", ("bottom", "bottom_left", "bottom_right", "center", "top", "top_left", "top_right")),
    EnvField("QUICK_INPUT_MARGIN", "32", int, "Overlay", "Input screen margin", "Distance between the command box and screen edges, in pixels."),
    EnvField("UI_RING_RADIUS", "72", int, "Overlay", "Ring Radius", "Base radius of the Maya ring."),
    EnvField("UI_RING_THICKNESS", "18", int, "Overlay", "Ring Thickness", "Base stroke thickness of the Maya ring."),
    EnvField("UI_COLOR_IDLE", "#d8dee6", str, "Overlay", "Idle Ring Color", "Ring accent color while Maya is idle. Pick it from the color selector."),
    EnvField("UI_COLOR_READY", "#62ff8f", str, "Overlay", "Ready Ring Color", "Ring accent color while Maya is ready. Pick it from the color selector."),
    EnvField("UI_COLOR_HEARING", "#ffd75e", str, "Overlay", "Hearing Ring Color", "Ring accent color while Maya is listening. Pick it from the color selector."),
    EnvField("UI_COLOR_SPEAKING", "#9ed0ff", str, "Overlay", "Speaking Ring Color", "Ring accent color while Maya is speaking. Pick it from the color selector."),
    EnvField("UI_COLOR_ERROR", "#ff6b6b", str, "Overlay", "Error Ring Color", "Ring accent color when Maya hits an error. Pick it from the color selector."),
    EnvField("UI_COLOR_CORE", "#ffffff", str, "Overlay", "Core Ring Color", "Main inner ring color. Pick it from the color selector."),
    EnvField('RESPONSE_BUBBLE_MODE', 'hotkey', str, "Text replies", 'Show replies', 'Show text replies after hotkey activation, always, or never.', ('hotkey', 'always', 'never')),
    EnvField('RESPONSE_BUBBLE_POSITION', 'bottom_right', str, "Text replies", 'Corner', 'Screen corner used for text replies.', ('bottom_right', 'bottom_left', 'top_right', 'top_left')),
    EnvField('RESPONSE_BUBBLE_MARGIN', '6', int, "Text replies", 'Screen margin', 'Distance from the usable screen edges, in pixels.', ()),
    EnvField('RESPONSE_BUBBLE_WIDTH', '440', int, "Text replies", 'Maximum width', 'Maximum reply width in pixels; short replies stay compact.', ()),
    EnvField('RESPONSE_BUBBLE_HEIGHT_PERCENT', '45', int, "Text replies", 'Maximum screen height (%)', 'Limit the reply height; longer text scrolls.', ()),
    EnvField('RESPONSE_BUBBLE_FONT_SIZE', '14', int, "Text replies", 'Text size', 'Reply font size in pixels.', ()),
    EnvField('RESPONSE_BUBBLE_OPACITY', '92', int, "Text replies", 'Background opacity (%)', '100 is solid; lower values reveal more of the background.', ()),
    EnvField('RESPONSE_BUBBLE_RADIUS', '16', int, "Text replies", 'Rounded corners', 'Corner radius in pixels.', ()),
    EnvField('RESPONSE_BUBBLE_MIN_SECONDS', '6', float, "Text replies", 'Minimum display time', 'Minimum seconds before a reply disappears.', ()),
    EnvField('RESPONSE_BUBBLE_MAX_SECONDS', '120', float, "Text replies", 'Maximum display time', 'Maximum seconds for long replies.', ()),
    EnvField('RESPONSE_BUBBLE_MS_PER_CHAR', '65', int, "Text replies", 'Reading time per character', 'Milliseconds per character; higher values keep replies longer.', ()),
    EnvField("LOCAL_DIALOGUE_ENABLED", "false", str, "Conversation", "Local language model (experimental)", "Use the installed local model for open conversation, with contextual memory and native fallback. Loads on demand and sleeps after 3 minutes.", ("true", "false")),
    EnvField("DIALOGUE_ENABLED", "true", str, "Conversation", "Native context", "Connect topics, follow-up questions and recent app references using Maya's own engine.", ("true", "false")),
    EnvField("MAX_BACKUPS_PER_FILE", "5", int, "Files", "Max Backups Per File", "How many backups helper tools keep."),
    EnvField("VOCAB_PATH", "data/vocabulary.json", str, "Files", "Vocabulary Path", "Path to the learned vocabulary JSON file."),
    EnvField("MEMORY_PATH", "data/memory.json", str, "Files", "Memory Path", "Path to Maya's persistent memory JSON file."),
    EnvField("RESPONSES_PATH", "data/responses.json", str, "Files", "Responses Path", "Path to the response template catalog."),
    EnvField("APP_TEXT_PATH", "data/app_text.json", str, "Files", "App Text Path", "Path to the app text/config JSON file."),
    EnvField("APPS_PATH", "data/apps.json", str, "Files", "Apps Catalog Path", "Path to the allowed apps catalog JSON file."),
    EnvField("KNOWLEDGE_PATH", "data/learned_knowledge.json", str, "Files", "Knowledge Path", "Path to the learned knowledge JSON file."),
    EnvField("ROUTINE_PATH", "data/routine.json", str, "Files", "Routine Path", "Path to personal routine progress and settings."),
    EnvField("DEV_PROJECTS_PATH", "generated_projects", str, "Files", "Dev Projects Path", "Base folder where Maya creates generated development projects."),
)

ENV_FIELDS += tuple(EnvField(s.key, s.default, s.cast, s.category, s.label, s.help, s.options) for s in DIALOGUE_SETTINGS)

ENV_FIELD_MAP = {field.key: field for field in ENV_FIELDS}

ensure_runtime_layout()
load_dotenv(ENV_FILE)


def reload_env():
    load_dotenv(ENV_FILE, override=True)


def get_env(key, default=None, cast=str):
    value = os.getenv(key, default)
    # Desktop terminals may export an empty gettext LANGUAGE. It must not shadow
    # Maya's saved language and then become an invalid STT language argument.
    if key == 'LANGUAGE' and not str(value or '').strip():
        value = dotenv_values(ENV_FILE).get('LANGUAGE') or default or 'en'

    if value is None:
        return None

    try:
        return cast(value)
    except Exception as diagnostic_error:
        report_error("config_value", diagnostic_error, operation="config.get_env", notify=False)
        return default


def get_path(key, default):
    raw_value = get_env(key, default)
    path = Path(raw_value)

    if path.is_absolute():
        return path

    if key == "VOSK_MODEL_PATH":
        return get_resource_path(path)

    return get_runtime_path(path)


def get_env_fields():
    return ENV_FIELDS


def get_env_defaults():
    return {field.key: field.default for field in ENV_FIELDS}


def get_env_values():
    file_values = {
        key: value
        for key, value in dotenv_values(ENV_FILE).items()
        if value is not None
    }
    values = {}
    for field in ENV_FIELDS:
        values[field.key] = file_values.get(field.key, str(get_env(field.key, field.default)))
    return values


NUMERIC_LIMITS = {
    "WHISPER_THREADS": (1, 32),
    "WAKE_DURATION": (1, 300), "VOICE_SAMPLE_RATE": (8000, 192000),
    "VOICE_BLOCK_SIZE": (1600, 16000), "VOICE_ENDPOINT_SILENCE_MS": (200, 3000),
    "VOICE_NOISE_GATE": (20, 20000), "TTS_RATE": (80, 400), "TTS_VOLUME": (0, 1),
    "INITIAL_SCALE": (0.1, 3), "INITIAL_MONITOR": (1, 32),
    "WINDOW_WIDTH": (80, 2000), "WINDOW_HEIGHT": (80, 2000), "WINDOW_MARGIN": (0, 1000),
}


NUMERIC_LIMITS.update({s.key: s.bounds for s in DIALOGUE_SETTINGS if s.bounds})

def save_env_values(values):
    current = get_env_values()
    cleaned = {}
    for field in ENV_FIELDS:
        raw = values.get(field.key, current.get(field.key, field.default))
        value = "" if raw is None else str(raw).strip()
        value = value or field.default
        if field.options and value not in field.options:
            raise ValueError(f"{field.key} must be one of: {', '.join(field.options)}")
        if field.cast in (int, float):
            try:
                number = field.cast(value)
                if not math.isfinite(number):
                    raise ValueError('must be finite')
                lower, upper = NUMERIC_LIMITS.get(field.key, (0, float('inf')))
                if not lower <= number <= upper:
                    raise ValueError(f'must be between {lower} and {upper}')
            except (ValueError, TypeError, OverflowError) as error:
                raise ValueError(f"{field.key}: {error}") from error
        cleaned[field.key] = value

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.maya-env-', dir=ENV_FILE.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            if ENV_FILE.exists():
                stream.write(ENV_FILE.read_bytes())
                os.fchmod(stream.fileno(), ENV_FILE.stat().st_mode & 0o777)
        for key, value in cleaned.items():
            set_key(temporary, key, value, quote_mode='auto')
        with open(temporary, 'rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, ENV_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    reload_env()
