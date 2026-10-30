from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDefinition:
    code: str
    title: str
    action: str


ERRORS = {
    "unexpected": ErrorDefinition("MAY-0001", 'Unexpected internal error', "Consulte o traceback no log."),
    "config_permission": ErrorDefinition("MAY-0101", 'Cannot access configuration', 'Close duplicate instances and check the Maya data folder.'),
    "config_layout": ErrorDefinition("MAY-0102", 'Invalid data structure', 'Restore or recreate Maya local files.'),
    "config_value": ErrorDefinition("MAY-0103", 'Invalid configuration', 'Correct the indicated setting.'),
    "single_instance": ErrorDefinition("MAY-0201", 'Instance lock failed', 'Restart Maya; if the problem persists, stop older instances.'),
    "hotkey": ErrorDefinition("MAY-0202", 'Global shortcut unavailable', 'Check keyboard permissions and pynput.'),
    "microphone_dependency": ErrorDefinition("MAY-0301", 'Audio dependency unavailable', 'Reinstall speech dependencies.'),
    "microphone_device": ErrorDefinition("MAY-0302", 'Microphone not found', 'Select or connect an input device.'),
    "voice_model": ErrorDefinition("MAY-0303", 'Recognition model unavailable', "Confira VOSK_MODEL_PATH e os arquivos do modelo."),
    "voice_runtime": ErrorDefinition("MAY-0304", 'Speech recognition failed', 'Check the microphone and audio log.'),
    "noise_suppression": ErrorDefinition("MAY-0305", 'Noise processing failed', 'Review noise-suppressor settings.'),
    "tts_init": ErrorDefinition("MAY-0401", 'Voice input not initialized', 'Check the configured speech engine.'),
    "tts_runtime": ErrorDefinition("MAY-0402", 'Speech playback failed', 'Try another speech engine and inspect the log.'),
    "ui_init": ErrorDefinition("MAY-0501", 'Interface not initialized', "Confira PySide6, Qt e as DLLs do pacote."),
    "ui_runtime": ErrorDefinition("MAY-0502", 'Interface failure', "Reabra a Maya e consulte o log."),
    "input_pipeline": ErrorDefinition("MAY-0601", 'Failed to process input', 'Repeat the command and inspect the log.'),
    "memory_storage": ErrorDefinition("MAY-0701", 'Local memory unavailable', 'Check access to the data folder.'),
    "routine_storage": ErrorDefinition("MAY-0702", 'Local routine unavailable', 'Check data/routine.json and its permissions.'),
    "app_launch": ErrorDefinition("MAY-0801", 'Application could not be opened', 'Check the application path and permissions.'),
    "web_request": ErrorDefinition("MAY-0901", 'Web service unavailable', 'Check the connection and try again.'),
    "installer": ErrorDefinition("MAY-1001", 'Installer failed', 'Inspect the installer log.'),
    "app_control": ErrorDefinition("MAY-1002", 'Executable blocked by Windows', 'Sign the executable or allow it through the applicable security policy.'),
}


def error_code(key):
    return ERRORS.get(key, ERRORS["unexpected"])


def classify_exception(error, context=""):
    context = (context or "").lower()
    if isinstance(error, PermissionError) and ("config" in context or ".env" in str(error).lower()):
        return ERRORS["config_permission"]
    if "qt" in str(error).lower() or "renderer" in context:
        return ERRORS["ui_init"]
    return ERRORS["unexpected"]


def format_error(key, detail=None):
    definition = error_code(key)
    suffix = f": {detail}" if detail else ""
    return f"[{definition.code}] {definition.title}{suffix}"
