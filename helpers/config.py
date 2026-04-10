import os
import shutil
import sys
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

    for relative_path in (
        ".env",
        "data/apps.json",
        "data/learned_knowledge.json",
        "data/memory.json",
        "data/responses.json",
        "data/vocabulary.json",
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
    EnvField("LANGUAGE", "en", str, "General", "Language", "Assistant language code."),
    EnvField("WAKE_DURATION", "6.0", float, "Wake", "Wake Duration", "How long Maya stays awake after interaction."),
    EnvField("WAKE_RESPONSE_COOLDOWN", "2.5", float, "Wake", "Wake Response Cooldown", "Minimum delay between spoken wake responses."),
    EnvField("WAKE_RESPONSE_TEXT", "yes?", str, "Wake", "Wake Response Text", "Fallback spoken answer when Maya wakes."),
    EnvField("WAKE_RESPONSE_OPTIONS", "", str, "Wake", "Wake Response Options", "Pipe-separated wake phrases, for example: yes?|what's up?"),
    EnvField("SPEAK_WAKE_RESPONSE_ON_CLAP", "true", str, "Wake", "Speak On Clap", "Whether Maya speaks after double clap.", ("true", "false")),
    EnvField("SPEAK_WAKE_RESPONSE_ON_HOTKEY", "true", str, "Wake", "Speak On Hotkey", "Whether Maya speaks after hotkey wake.", ("true", "false")),
    EnvField("STARTUP_GREETING_ENABLED", "true", str, "Wake", "Startup Greeting", "Whether Maya greets you after login/startup.", ("true", "false")),
    EnvField("STARTUP_GREETING_DELAY", "8.0", float, "Wake", "Startup Greeting Delay", "Delay in seconds before the startup greeting."),
    EnvField("STARTUP_BRIEF_RESPONSE_WINDOW", "20.0", float, "Wake", "Startup Brief Response Window", "How long Maya stays awake waiting for your answer to the startup brief."),
    EnvField("DAILY_BRIEF_LOCATION", "", str, "Wake", "Daily Brief Location", "Optional weather location for the startup daily brief."),
    EnvField("VOICE_IGNORE_COOLDOWN", "1.2", float, "Voice", "Voice Ignore Cooldown", "Cooldown for low-signal voice input suppression."),
    EnvField("VOICE_SAMPLE_RATE", "16000", int, "Voice", "Voice Sample Rate", "Recognizer microphone sample rate."),
    EnvField("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15", str, "Voice", "Vosk Model Path", "Relative path to the Vosk speech model."),
    EnvField("CLAP_THRESHOLD", "150", int, "Audio", "Clap Threshold", "Minimum RMS to count as a clap."),
    EnvField("CLAP_COOLDOWN", "0.18", float, "Audio", "Clap Cooldown", "Minimum delay between clap detections."),
    EnvField("CLAP_WINDOW", "0.75", float, "Audio", "Double Clap Window", "Maximum delay between claps for wake."),
    EnvField("TTS_RATE", "180", int, "Speech", "TTS Rate", "Speech rate for pyttsx3."),
    EnvField("TTS_VOLUME", "1.0", float, "Speech", "TTS Volume", "Speech volume from 0.0 to 1.0."),
    EnvField("TTS_VOICE_ID", "", str, "Speech", "TTS Voice ID", "Specific pyttsx3 voice id. Leave blank to auto-pick."),
    EnvField("TTS_VOICE_GENDER", "female", str, "Speech", "Preferred Voice Gender", "Voice preference when no id is set.", ("female", "male", "neutral")),
    EnvField("WINDOW_CAPTION", "maya", str, "Overlay", "Window Caption", "Overlay window title."),
    EnvField("WINDOW_WIDTH", "260", int, "Overlay", "Window Width", "Base overlay width."),
    EnvField("WINDOW_HEIGHT", "260", int, "Overlay", "Window Height", "Base overlay height."),
    EnvField("WINDOW_MARGIN", "32", int, "Overlay", "Window Margin", "Distance from screen edges."),
    EnvField("INITIAL_POSITION", "top_right", str, "Overlay", "Initial Position", "Overlay anchor position.", ("top_left", "top", "top_right", "left", "center", "right", "bottom_left", "bottom", "bottom_right")),
    EnvField("INITIAL_MONITOR", "2", int, "Overlay", "Initial Monitor", "1-based monitor number for the overlay."),
    EnvField("INITIAL_SCALE", "0.5", float, "Overlay", "Initial Scale", "Initial overlay scale factor."),
    EnvField("QUICK_INPUT_WIDTH", "420", int, "Overlay", "Quick Input Width", "Quick input popup width."),
    EnvField("QUICK_INPUT_HEIGHT", "92", int, "Overlay", "Quick Input Height", "Quick input popup height."),
    EnvField("UI_RING_RADIUS", "72", int, "Overlay", "Ring Radius", "Base radius of the Maya ring."),
    EnvField("UI_RING_THICKNESS", "18", int, "Overlay", "Ring Thickness", "Base stroke thickness of the Maya ring."),
    EnvField("MAX_BACKUPS_PER_FILE", "5", int, "Files", "Max Backups Per File", "How many backups helper tools keep."),
    EnvField("VOCAB_PATH", "data/vocabulary.json", str, "Files", "Vocabulary Path", "Path to the learned vocabulary JSON file."),
    EnvField("MEMORY_PATH", "data/memory.json", str, "Files", "Memory Path", "Path to Maya's persistent memory JSON file."),
    EnvField("RESPONSES_PATH", "data/responses.json", str, "Files", "Responses Path", "Path to the response template catalog."),
    EnvField("APPS_PATH", "data/apps.json", str, "Files", "Apps Catalog Path", "Path to the allowed apps catalog JSON file."),
    EnvField("KNOWLEDGE_PATH", "data/learned_knowledge.json", str, "Files", "Knowledge Path", "Path to the learned knowledge JSON file."),
    EnvField("DEV_PROJECTS_PATH", "generated_projects", str, "Files", "Dev Projects Path", "Base folder where Maya creates generated development projects."),
)

ENV_FIELD_MAP = {field.key: field for field in ENV_FIELDS}

ensure_runtime_layout()
load_dotenv(ENV_FILE)


def reload_env():
    load_dotenv(ENV_FILE, override=True)


def get_env(key, default=None, cast=str):
    value = os.getenv(key, default)

    if value is None:
        return None

    try:
        return cast(value)
    except Exception:
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


def save_env_values(values):
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_FILE.exists():
        ENV_FILE.touch()

    for field in ENV_FIELDS:
        raw_value = values.get(field.key, field.default)
        clean_value = "" if raw_value is None else str(raw_value).strip()

        if clean_value == "":
            clean_value = field.default

        if field.options and clean_value not in field.options:
            raise ValueError(f"{field.key} must be one of: {', '.join(field.options)}")

        if field.cast in (int, float):
            try:
                field.cast(clean_value)
            except Exception as error:
                raise ValueError(f"{field.key} must be a valid {field.cast.__name__}") from error

        set_key(str(ENV_FILE), field.key, clean_value, quote_mode="auto")

    reload_env()
