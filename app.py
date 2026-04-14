import os
import queue
import time
import random
import sys
import threading
import datetime
import re
import unicodedata
import traceback
from pathlib import Path


def _configure_qt_platform():
    if not sys.platform.startswith("linux"):
        return

    if os.getenv("QT_QPA_PLATFORM"):
        return

    display = (os.getenv("DISPLAY") or "").strip()
    wayland_display = (os.getenv("WAYLAND_DISPLAY") or "").strip()
    session_type = (os.getenv("XDG_SESSION_TYPE") or "").strip().lower()

    if session_type == "wayland" and not wayland_display and display:
        os.environ["QT_QPA_PLATFORM"] = "xcb"


_configure_qt_platform()


def _runtime_log_path():
    if getattr(sys, "frozen", False):
        if sys.platform.startswith("win"):
            base_dir = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")) / "maya"
        elif sys.platform == "darwin":
            base_dir = Path.home() / "Library" / "Application Support" / "maya"
        else:
            base_dir = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "maya"
    else:
        base_dir = Path(__file__).resolve().parent

    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "startup-error.log"


def _log_unhandled_exception(exc_type, exc_value, exc_traceback):
    try:
        log_path = _runtime_log_path()
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n[{datetime.datetime.now().isoformat()}] Unhandled exception\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)
    except Exception:
        pass

    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = _log_unhandled_exception


def _log_thread_exception(args):
    _log_unhandled_exception(args.exc_type, args.exc_value, args.exc_traceback)


if hasattr(threading, "excepthook"):
    threading.excepthook = _log_thread_exception

from output.renderer import Renderer
from core.process import Process
from core.memory import Memory
from input.voice import Voice
from core import vocabulary_manager
from input.clap_detector import ClapDetector
from output.speaker import Speaker
from helpers.config import get_env, reload_env, save_env_values
from helpers.app_launcher import AppLauncher
from helpers.app_text import load_app_text
from helpers.dev_assistant import DevAssistant
from helpers.global_hotkey import GlobalHotkeyListener
from helpers.runtime_console import RuntimeConsole, should_enable_runtime_console
from helpers.web_assistant import WebAssistant
from helpers.spotify_assistant import SpotifyAssistant


RUNTIME_CONSOLE = RuntimeConsole()
RUNTIME_CONSOLE.sync(should_enable_runtime_console())


class App:
    def __init__(self):
        self.app_text = load_app_text()
        vocabulary_manager.load_vocabulary()
        self.events = queue.Queue()

        self.memory = Memory()
        self.memory.load()

        self.process = Process()
        self.process.parent = self
        self.process.memory = self.memory
        self.process.app_launcher = AppLauncher()
        self.process.dev_assistant = DevAssistant()
        self.process.web_assistant = WebAssistant()
        self.process.spotify_assistant = SpotifyAssistant()
        self.hotkey_listener = GlobalHotkeyListener()

        self.DEBUG_MODE = get_env("DEBUG_MODE", "false").lower() == "true"
        RUNTIME_CONSOLE.sync(self.DEBUG_MODE)
        self.UI_MODE = get_env("UI_MODE", "maya")
        self.LANGUAGE = get_env("LANGUAGE", "en")
        self.WAKE_RESPONSE_TEXT = get_env("WAKE_RESPONSE_TEXT", "yes?")
        wake_response_options = get_env("WAKE_RESPONSE_OPTIONS", "")
        self.wake_response_options = [
            option.strip() for option in wake_response_options.split("|")
            if option.strip()
        ]
        self.speak_wake_response = get_env("SPEAK_WAKE_RESPONSE", "true").lower() == "true"
        self.speak_wake_response_on_clap = get_env("SPEAK_WAKE_RESPONSE_ON_CLAP", "true").lower() == "true"
        self.speak_wake_response_on_hotkey = get_env("SPEAK_WAKE_RESPONSE_ON_HOTKEY", "true").lower() == "true"
        self.microphone_enabled = get_env("MICROPHONE_ENABLED", "true").lower() == "true"
        self.speech_muted = get_env("SPEECH_MUTED", "false").lower() == "true"

        self.speaker = self._create_speaker()
        self.clap_detector = self._create_clap_detector()
        self.voice = self._create_voice()

        self.voice_active = False
        self.current_response_source = None
        self.wake_duration = get_env("WAKE_DURATION", 6.0, float)
        self.wake_response_cooldown = get_env("WAKE_RESPONSE_COOLDOWN", 2.5, float)
        self.maya_awake_until = 0.0
        self.last_wake_response_at = 0.0
        self.last_ignored_voice_at = 0.0
        self.ignored_voice_cooldown = get_env("VOICE_IGNORE_COOLDOWN", 1.2, float)
        self.startup_greeting_enabled = get_env("STARTUP_GREETING_ENABLED", "true").lower() == "true"
        self.startup_greeting_delay = get_env("STARTUP_GREETING_DELAY", 8.0, float)
        self.startup_brief_response_window = get_env("STARTUP_BRIEF_RESPONSE_WINDOW", 20.0, float)
        self.daily_brief_location = get_env("DAILY_BRIEF_LOCATION", "")
        self.awaiting_startup_brief_response = False
        self.pending_context_action = None

        self.renderer = Renderer(
            self.events,
            submit_input_callback=self.handle_input,
            periodic_callback=self.update_app_state,
            keep_awake_callback=self.keep_awake,
            settings_apply_callback=self.apply_user_settings,
        )

        clap_started = False
        if self.microphone_enabled:
            clap_started = self.clap_detector.start(
                on_double_clap=self.handle_double_clap,
                on_clap=self.handle_single_clap
            )
        hotkey_started = self.hotkey_listener.start_pgdown_end(self.handle_hotkey_wake)

        if not hotkey_started:
            reason = getattr(self.hotkey_listener, "last_error", None) or "could not register PgDown + End"
            print(f"global hotkey unavailable: {reason}")

        if not clap_started and self.clap_detector.last_error:
            print(f"microphone wake unavailable: {self.clap_detector.last_error}")

        if not hotkey_started and not clap_started:
            print("no wake method is currently available, opening Maya on screen")
            self.send_event("app_foreground", None)
            self.send_event("app_show_quick_input", None)

        self._schedule_startup_greeting()
        self.renderer.run()

    @staticmethod
    def _normalize_command(text):
        normalized = unicodedata.normalize("NFKD", (text or "").strip().lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.replace("-", " ").replace("_", " ")
        normalized = re.sub(r"[^a-z0-9\\s']+", " ", normalized)
        return " ".join(normalized.split())

    def _is_settings_command(self, text):
        normalized = self._normalize_command(text)
        return any(self.process.contains_phrase(normalized, option) for option in self._app_text_values("settings_commands"))

    def _create_speaker(self):
        default_rate = 150 if sys.platform.startswith("linux") else 180
        return Speaker(
            rate=get_env("TTS_RATE", default_rate, int),
            volume=get_env("TTS_VOLUME", 1.0, float),
            voice_id=get_env("TTS_VOICE_ID"),
            language=self.LANGUAGE,
            muted=self.speech_muted,
            engine_preference=get_env("TTS_ENGINE", "auto"),
        )

    def _create_clap_detector(self):
        return ClapDetector(
            threshold=get_env("CLAP_THRESHOLD", 150, int),
            cooldown=get_env("CLAP_COOLDOWN", 0.18, float),
            double_clap_window=get_env("CLAP_WINDOW", 0.75, float),
        )

    def _create_voice(self):
        return Voice(
            model_path=get_env("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15"),
            sample_rate=get_env("VOICE_SAMPLE_RATE", 16000, int),
        )

    def _is_portuguese(self):
        return str(self.LANGUAGE).lower().startswith("pt")

    def _reload_app_text(self):
        self.app_text = load_app_text()

    def _app_text_values(self, key):
        values = self.app_text.get(key, [])
        return tuple(item.strip() for item in values if isinstance(item, str) and item.strip())

    def _app_text_localized_values(self, key):
        values = self.app_text.get(key, {})
        if not isinstance(values, dict):
            return ()

        if self._is_portuguese():
            selected = values.get("pt-BR") or values.get("pt") or values.get("en", [])
        else:
            selected = values.get("en") or []

        return tuple(item.strip() for item in selected if isinstance(item, str) and item.strip())

    def _app_message(self, key, **values):
        messages = self.app_text.get("messages", {})
        entry = messages.get(key, {})
        if not isinstance(entry, dict):
            template = ""
        elif self._is_portuguese():
            template = entry.get("pt-BR") or entry.get("pt") or entry.get("en", "")
        else:
            template = entry.get("en", "")
        return template.format(**values) if values else template

    def apply_runtime_settings(self):
        reload_env()
        self._reload_app_text()

        self.DEBUG_MODE = get_env("DEBUG_MODE", "false").lower() == "true"
        RUNTIME_CONSOLE.sync(self.DEBUG_MODE)
        self.UI_MODE = get_env("UI_MODE", "maya")
        self.LANGUAGE = get_env("LANGUAGE", "en")
        self.WAKE_RESPONSE_TEXT = get_env("WAKE_RESPONSE_TEXT", "yes?")
        wake_response_options = get_env("WAKE_RESPONSE_OPTIONS", "")
        self.wake_response_options = [
            option.strip() for option in wake_response_options.split("|")
            if option.strip()
        ]
        self.speak_wake_response = get_env("SPEAK_WAKE_RESPONSE", "true").lower() == "true"
        self.speak_wake_response_on_clap = get_env("SPEAK_WAKE_RESPONSE_ON_CLAP", "true").lower() == "true"
        self.speak_wake_response_on_hotkey = get_env("SPEAK_WAKE_RESPONSE_ON_HOTKEY", "true").lower() == "true"
        self.microphone_enabled = get_env("MICROPHONE_ENABLED", "true").lower() == "true"
        self.speech_muted = get_env("SPEECH_MUTED", "false").lower() == "true"
        self.wake_duration = get_env("WAKE_DURATION", 6.0, float)
        self.wake_response_cooldown = get_env("WAKE_RESPONSE_COOLDOWN", 2.5, float)
        self.ignored_voice_cooldown = get_env("VOICE_IGNORE_COOLDOWN", 1.2, float)
        self.startup_greeting_enabled = get_env("STARTUP_GREETING_ENABLED", "true").lower() == "true"
        self.startup_greeting_delay = get_env("STARTUP_GREETING_DELAY", 8.0, float)
        self.startup_brief_response_window = get_env("STARTUP_BRIEF_RESPONSE_WINDOW", 20.0, float)
        self.daily_brief_location = get_env("DAILY_BRIEF_LOCATION", "")

        self.process.DEBUG_MODE = self.DEBUG_MODE
        self.process.UI_MODE = self.UI_MODE
        self.process.LANGUAGE = self.LANGUAGE

        if hasattr(self, "speaker") and self.speaker is not None:
            self.speaker.stop()
            self.speaker.shutdown()
        self.speaker = self._create_speaker()
        self.speaker.set_muted(self.speech_muted)

        voice_was_active = getattr(self, "voice_active", False)
        if hasattr(self, "voice") and self.voice is not None:
            self.voice.stop()
        self.voice = self._create_voice()
        if voice_was_active and self.microphone_enabled:
            started = self.voice.start_background(
                on_final_text=self.handle_voice_input,
                on_partial_text=self.handle_partial_voice,
                on_status_change=self.handle_voice_status,
            )
            self.voice_active = bool(started)
            self.send_event("voice_status", "ready" if started else "unavailable")
        else:
            self.voice_active = False
            self.send_event("voice_status", "idle")

        if hasattr(self, "clap_detector") and self.clap_detector is not None:
            self.clap_detector.stop()
        self.clap_detector = self._create_clap_detector()
        clap_started = False
        if self.microphone_enabled:
            clap_started = self.clap_detector.start(
                on_double_clap=self.handle_double_clap,
                on_clap=self.handle_single_clap,
            )
        if not clap_started and self.clap_detector.last_error:
            print(f"microphone wake unavailable: {self.clap_detector.last_error}")

        if hasattr(self, "renderer") and self.renderer is not None:
            self.renderer.apply_runtime_settings()

    def apply_user_settings(self, values):
        try:
            save_env_values(values)
            self.apply_runtime_settings()
            return True, self._app_message("settings_applied")
        except Exception as error:
            prefix = self._app_message("settings_apply_failed_prefix")
            return False, f"{prefix}: {error}"

    def get_wake_response_text(self):
        if self.wake_response_options:
            return random.choice(self.wake_response_options)
        return self.WAKE_RESPONSE_TEXT

    def _schedule_startup_greeting(self):
        if not self.startup_greeting_enabled or not sys.platform.startswith("linux"):
            return

        timer = threading.Timer(self.startup_greeting_delay, self._deliver_startup_greeting)
        timer.daemon = True
        timer.start()

    def _deliver_startup_greeting(self):
        options = self._app_text_localized_values("startup_greeting_options")
        greeting = random.choice(options)
        self.awaiting_startup_brief_response = True
        self.maya_awake_until = time.time() + self.startup_brief_response_window
        self.send_event("response_text", greeting)
        self.send_event("app_foreground", None)
        self.send_event("voice_status", "speaking")
        self.speaker.stop()
        self.speaker.speak(greeting)
        listen_delay = max(4.0, min(len(greeting) / 12.0, 8.0))
        timer = threading.Timer(listen_delay, self._enable_startup_brief_listening)
        timer.daemon = True
        timer.start()

    def _enable_startup_brief_listening(self):
        if not self.microphone_enabled or not self.awaiting_startup_brief_response or self.voice_active:
            return

        started = self.voice.start_background(
            on_final_text=self.handle_voice_input,
            on_partial_text=self.handle_partial_voice,
            on_status_change=self.handle_voice_status,
        )
        self.voice_active = bool(started)
        self.send_event("voice_status", "ready" if started else "unavailable")

    def _looks_like_startup_brief_yes(self, text):
        normalized = self._normalize_command(text)
        return any(self.process.contains_phrase(normalized, option) for option in self._app_text_values("startup_brief_accept_inputs"))

    def _looks_like_startup_brief_no(self, text):
        normalized = self._normalize_command(text)
        return any(self.process.contains_phrase(normalized, option) for option in self._app_text_values("startup_brief_decline_inputs"))

    def _looks_like_action_yes(self, text):
        normalized = self._normalize_command(text)
        return any(self.process.contains_phrase(normalized, option) for option in self._app_text_values("action_confirm_inputs"))

    def _looks_like_action_no(self, text):
        normalized = self._normalize_command(text)
        return any(self.process.contains_phrase(normalized, option) for option in self._app_text_values("action_decline_inputs"))

    def _clear_pending_context_action(self):
        self.pending_context_action = None

    def _set_pending_context_action(
        self,
        event_name,
        prompt,
        payload=None,
        timeout=18.0,
        confirm_response=None,
        decline_response=None,
    ):
        self.pending_context_action = {
            "event": event_name,
            "payload": payload,
            "expires_at": time.time() + timeout,
            "confirm_response": confirm_response or self._app_message("pending_confirm_default"),
            "decline_response": decline_response or self._app_message("pending_decline_default"),
        }
        self.send_event("response_text", prompt)
        self.send_event("voice_status", "speaking")
        self.speaker.stop()
        self.speaker.speak(prompt)
        return prompt

    def _consume_pending_context_action(self, text):
        if not self.pending_context_action:
            return None

        if time.time() > self.pending_context_action.get("expires_at", 0):
            self._clear_pending_context_action()
            return None

        if self._looks_like_action_yes(text):
            action = dict(self.pending_context_action)
            self._clear_pending_context_action()
            self.send_event(action["event"], action.get("payload"))
            response = action.get("confirm_response") or self._app_message("pending_confirm_default")
            self.send_event("response_text", response)
            self.send_event("voice_status", "speaking")
            self.speaker.stop()
            self.speaker.speak(response)
            return response

        if self._looks_like_action_no(text):
            action = dict(self.pending_context_action)
            self._clear_pending_context_action()
            response = action.get("decline_response") or self._app_message("pending_decline_default")
            self.send_event("response_text", response)
            self.send_event("voice_status", "speaking")
            self.speaker.stop()
            self.speaker.speak(response)
            return response

        return None

    def _looks_like_daily_brief_request(self, text):
        normalized = self._normalize_command(text)
        patterns = [
            r"(?:news|headlines).*(?:today|hoje)",
            r"(?:today|hoje).*(?:news|headlines|noticias|noticias)",
            r"(?:me fale|fala|tell me|show me|quero|manda).*(?:noticias|noticias|news|headlines).*(?:hoje|today)?",
            r"(?:daily brief|brief do dia|resumo do dia|resumo de hoje)",
        ]
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    def _looks_like_thoughtful_suggestion_case(self, text):
        normalized = self._normalize_command(text)
        patterns = [
            r"\bestou pensativo\b",
            r"\bto pensativo\b",
            r"\bt[oô] pensativo\b",
            r"\bi am thinking a lot\b",
            r"\bi'm thinking a lot\b",
            r"\bestou triste\b",
            r"\bto triste\b",
            r"\bt[oô] triste\b",
            r"\bestou meio mal\b",
            r"\bestou ansioso\b",
            r"\bto ansioso\b",
            r"\bt[oô] ansioso\b",
            r"\bestou pensando demais\b",
            r"\bto pensando demais\b",
            r"\bt[oô] pensando demais\b",
            r"\bestou sobrecarregado\b",
            r"\bto sobrecarregado\b",
            r"\bt[oô] sobrecarregado\b",
            r"\bi'm overthinking\b",
            r"\bi am overthinking\b",
            r"\bi can't stop thinking\b",
        ]
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    def _looks_like_dev_mode_suggestion_case(self, text):
        normalized = self._normalize_command(text)
        patterns = [
            r"\bquero codar\b",
            r"\bvou codar\b",
            r"\bpreciso codar\b",
            r"\bquero programar\b",
            r"\bvou programar\b",
            r"\bpreciso programar\b",
            r"\bpreciso focar\b",
            r"\bquero focar\b",
            r"\bestou indo trabalhar\b",
            r"\bquero trabalhar\b",
            r"\bi need to focus\b",
            r"\bi want to code\b",
            r"\bi'm going to code\b",
            r"\bi am going to code\b",
            r"\bi need to work\b",
            r"\blet's code\b",
        ]
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    def _build_daily_brief_text(self):
        now = datetime.datetime.now()
        date_text = now.strftime("%B %d")
        time_text = now.strftime("%H:%M")

        weather_text = self.process.web_assistant.get_weather_brief(self.daily_brief_location)
        headlines = self.process.web_assistant.get_top_news_headlines(limit=3)

        if not weather_text and not headlines:
            return None

        parts = [
            self._app_message("daily_brief_date", date_text=date_text),
            self._app_message("daily_brief_time", time_text=time_text),
        ]
        if weather_text:
            parts.append(self._app_message("daily_brief_weather", weather_text=weather_text))
        if headlines:
            joined = "; ".join(headlines[:3])
            parts.append(self._app_message("daily_brief_headlines", headlines=joined))

        return " ".join(parts)

    def _speak_daily_brief_async(self):
        def worker():
            brief = self._build_daily_brief_text()
            if not brief:
                options = self._app_text_localized_values("startup_brief_error_options")
                brief = random.choice(options)
            self.send_event("response_text", brief)
            self.send_event("voice_status", "speaking")
            self.speaker.stop()
            self.speaker.speak(brief)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def wake_maya(self, trigger_source="clap"):
        now = time.time()
        if now < self.maya_awake_until:
            self.maya_awake_until = now + self.wake_duration
            return

        self.maya_awake_until = now + self.wake_duration

        self.send_event("app_foreground", None)
        self.send_event("double_clap", None)

        should_speak_for_source = self.speak_wake_response and (
            (trigger_source == "clap" and self.speak_wake_response_on_clap)
            or (trigger_source == "hotkey" and self.speak_wake_response_on_hotkey)
        )
        should_speak_wake_response = should_speak_for_source and (now - self.last_wake_response_at) >= self.wake_response_cooldown
        if should_speak_wake_response:
            wake_response_text = self.get_wake_response_text()
            self.last_wake_response_at = now
            self.send_event("response_text", wake_response_text)
            self.current_response_source = "system"
            self.speaker.stop()
            self.send_event("voice_status", "speaking")
            self.speaker.speak(wake_response_text)

        if self.microphone_enabled and not self.voice_active:
            started = self.voice.start_background(
                on_final_text=self.handle_voice_input,
                on_partial_text=self.handle_partial_voice,
                on_status_change=self.handle_voice_status
            )
            self.voice_active = bool(started)
            if not started:
                self.send_event("voice_status", "unavailable")
        else:
            self.send_event("voice_status", "ready")

    def sleep_maya(self):
        if not self.voice_active:
            self.send_event("app_sleep_ui", None)
            return

        self.voice.stop()
        self.voice_active = False
        self.send_event("voice_status", "idle")
        self.send_event("voice_partial", "")
        self.send_event("app_sleep_ui", None)
        if self.DEBUG_MODE:
            print("maya sleeping again")

    def update_app_state(self, dt):
        if self.voice_active and time.time() > self.maya_awake_until:
            self.sleep_maya()

    def keep_awake(self):
        self.maya_awake_until = time.time() + self.wake_duration

    def handle_single_clap(self, rms):
        if self.speaker.is_speaking:
            return
        self.send_event("clap", rms)

    def handle_double_clap(self):
        if self.speaker.is_speaking:
            return
        if self.DEBUG_MODE:
            print("WAKE UP MAYA")
        self.wake_maya(trigger_source="clap")

    def handle_hotkey_wake(self):
        self.wake_maya(trigger_source="hotkey")
        self.send_event("app_show_quick_input", None)

    def _is_actionable_voice_text(self, text):
        normalized = (text or "").strip().lower()
        if not normalized:
            return False

        if normalized in self._app_text_values("voice_filler_inputs"):
            return False

        if not hasattr(self.process, "tokenize"):
            return True

        tokens = self.process.tokenize(normalized)
        if not tokens:
            return False

        if tokens[0] in self._app_text_values("voice_question_starters"):
            return True

        if len(tokens) == 1 and normalized not in {"hello", "hi", "hey", "thanks", "thank", "bye"}:
            return False

        if not hasattr(self.process, "detect_patterns"):
            return True

        patterns = self.process.detect_patterns(normalized)
        actionable = any(
            value for key, value in patterns.items()
            if key not in {"asks_unknown", "app_alias", "move_app_target", "scale_app_target", "dev_project_spec",
                           "spotify_mode", "spotify_query", "spotify_spoken_query", "media_service",
                           "media_query", "media_browser_alias", "web_mode", "web_query", "web_browser_alias",
                           "preference_value", "preference_query_value", "fact_value", "fact_query_value", "user_name"}
            and isinstance(value, bool)
        )

        if actionable:
            return True

        return len(tokens) >= 4

    def _should_suppress_voice_response(self, text, response):
        normalized_response = (response or "").strip().lower()
        if not normalized_response.startswith(self._app_text_values("fallback_prefixes")):
            return False

        if not hasattr(self.process, "tokenize"):
            return True

        tokens = self.process.tokenize((text or "").lower())
        return len(tokens) <= 5

    def handle_voice_input(self, text):
        now = time.time()
        self.maya_awake_until = now + self.wake_duration
        if now - self.last_ignored_voice_at < self.ignored_voice_cooldown:
            if self.DEBUG_MODE:
                print("ignored voice input during cooldown:", repr(text))
            self.send_event("voice_final", "")
            return None

        if not self._is_actionable_voice_text(text):
            self.last_ignored_voice_at = now
            self.send_event("voice_final", "")
            if self.DEBUG_MODE:
                print("ignored low-signal voice input:", repr(text))
            return None

        self.send_event("voice_final", text)
        return self.handle_input(text, input_source="voice")

    def handle_partial_voice(self, text):
        self.maya_awake_until = time.time() + self.wake_duration
        if self.current_response_source == "voice":
            self.speaker.stop()
        self.send_event("voice_partial", text)

    def handle_voice_status(self, status):
        if self.voice_active:
            self.send_event("voice_status", status)

    def handle_input(self, text, input_source="text"):
        self.maya_awake_until = time.time() + self.wake_duration

        if self.awaiting_startup_brief_response:
            if self._looks_like_startup_brief_yes(text):
                self.awaiting_startup_brief_response = False
                self._speak_daily_brief_async()
                return None
            if self._looks_like_startup_brief_no(text):
                self.awaiting_startup_brief_response = False
                options = self._app_text_localized_values("startup_brief_decline_options")
                response = random.choice(options)
                self.send_event("response_text", response)
                self.send_event("voice_status", "speaking")
                self.speaker.stop()
                self.speaker.speak(response)
                return None

        pending_response = self._consume_pending_context_action(text)
        if pending_response is not None:
            return pending_response

        if self._is_settings_command(text):
            self.send_event("app_show_settings", None)
            return self._app_message("open_settings_response")

        if self._looks_like_daily_brief_request(text):
            response = self._app_message("daily_brief_request_response")
            self.send_event("response_text", response)
            self.send_event("voice_status", "speaking")
            self.speaker.stop()
            self.speaker.speak(response)
            self._speak_daily_brief_async()
            return response

        detected = self.process.detect_patterns((text or "").lower().strip())
        if (
            self._looks_like_thoughtful_suggestion_case(text)
            and not detected.get("thoughtful_workspace_action")
            and not detected.get("dev_workspace_action")
        ):
            return self._set_pending_context_action(
                "app_start_thoughtful_workspace",
                self._app_message("thoughtful_prompt"),
                confirm_response=self._app_message("thoughtful_confirm"),
                decline_response=self._app_message("thoughtful_decline"),
            )

        if (
            self._looks_like_dev_mode_suggestion_case(text)
            and not detected.get("dev_workspace_action")
            and not detected.get("thoughtful_workspace_action")
        ):
            return self._set_pending_context_action(
                "app_start_dev_workspace",
                self._app_message("dev_prompt"),
                confirm_response=self._app_message("dev_confirm"),
                decline_response=self._app_message("dev_decline"),
            )

        response = self.process.handle_input(text)
        self.memory.save()

        if self.DEBUG_MODE:
            print("input:", repr(text))
            print("response:", repr(response))

        if input_source == "voice" and self._should_suppress_voice_response(text, response):
            self.last_ignored_voice_at = time.time()
            if self.DEBUG_MODE:
                print("suppressed low-signal fallback response:", repr(response))
            return None

        if response:
            self.current_response_source = input_source
            if input_source != "text":
                self.speaker.stop()
            self.send_event("voice_status", "speaking")
            self.speaker.speak(response)

        return response

    def send_event(self, event, value=None):
        self.events.put((event, value))

    def get_data(self, data):
        if data == "fps":
            return self.renderer.get_fps()
        return None


if __name__ == "__main__":
    App()
