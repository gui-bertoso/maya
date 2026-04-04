from output.renderer import Renderer
from core.process import Process
from core.memory import Memory
from input.voice import Voice
import queue
from core import vocabulary_manager
from input.clap_detector import ClapDetector
import time
import random
from output.speaker import Speaker
from helpers.config import get_env
from helpers.app_launcher import AppLauncher
from helpers.dev_assistant import DevAssistant
from helpers.global_hotkey import GlobalHotkeyListener
from helpers.web_assistant import WebAssistant
from helpers.spotify_assistant import SpotifyAssistant


class App:
    VOICE_FILLER_INPUTS = {
        "huh",
        "uh",
        "um",
        "hmm",
        "hm",
        "ah",
        "eh",
        "yeah",
        "yes",
        "no",
        "okay",
        "ok",
        "maya",
    }

    VOICE_QUESTION_STARTERS = {
        "what",
        "what's",
        "whats",
        "who",
        "where",
        "when",
        "why",
        "how",
        "which",
    }

    FALLBACK_PREFIXES = (
        "i'm still learning",
        "i'm still figuring things out",
        "i'm not fully there yet",
    )

    def __init__(self):
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
        self.UI_MODE = get_env("UI_MODE", "maya")
        self.LANGUAGE = get_env("LANGUAGE", "en")
        self.WAKE_RESPONSE_TEXT = get_env("WAKE_RESPONSE_TEXT", "yes?")
        wake_response_options = get_env("WAKE_RESPONSE_OPTIONS", "")
        self.wake_response_options = [
            option.strip() for option in wake_response_options.split("|")
            if option.strip()
        ]
        self.speak_wake_response_on_clap = get_env("SPEAK_WAKE_RESPONSE_ON_CLAP", "true").lower() == "true"
        self.speak_wake_response_on_hotkey = get_env("SPEAK_WAKE_RESPONSE_ON_HOTKEY", "true").lower() == "true"

        self.speaker = Speaker(
            rate=get_env("TTS_RATE", 180, int),
            volume=get_env("TTS_VOLUME", 1.0, float),
            voice_id=get_env("TTS_VOICE_ID"),
            preferred_gender=get_env("TTS_VOICE_GENDER", "female"),
        )

        self.clap_detector = ClapDetector(
            threshold=get_env("CLAP_THRESHOLD", 150, int),
            cooldown=get_env("CLAP_COOLDOWN", 0.18, float),
            double_clap_window=get_env("CLAP_WINDOW", 0.75, float)
        )

        self.voice = Voice(
            model_path=get_env("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15"),
            sample_rate=get_env("VOICE_SAMPLE_RATE", 16000, int)
        )

        self.voice_active = False
        self.current_response_source = None
        self.wake_duration = get_env("WAKE_DURATION", 6.0, float)
        self.wake_response_cooldown = get_env("WAKE_RESPONSE_COOLDOWN", 2.5, float)
        self.maya_awake_until = 0.0
        self.last_wake_response_at = 0.0
        self.last_ignored_voice_at = 0.0
        self.ignored_voice_cooldown = get_env("VOICE_IGNORE_COOLDOWN", 1.2, float)

        self.renderer = Renderer(
            self.events,
            submit_input_callback=self.handle_input,
            periodic_callback=self.update_app_state,
            keep_awake_callback=self.keep_awake,
        )

        self.clap_detector.start(
            on_double_clap=self.handle_double_clap,
            on_clap=self.handle_single_clap
        )
        self.hotkey_listener.start_ctrl_m(self.handle_hotkey_wake)

        self.renderer.run()

    def get_wake_response_text(self):
        if self.wake_response_options:
            return random.choice(self.wake_response_options)
        return self.WAKE_RESPONSE_TEXT

    def wake_maya(self, trigger_source="clap"):
        now = time.time()
        if now < self.maya_awake_until:
            self.maya_awake_until = now + self.wake_duration
            return

        self.maya_awake_until = now + self.wake_duration

        self.send_event("app_foreground", None)
        self.send_event("double_clap", None)

        should_speak_for_source = (
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

        if not self.voice_active:
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

        if normalized in self.VOICE_FILLER_INPUTS:
            return False

        if not hasattr(self.process, "tokenize"):
            return True

        tokens = self.process.tokenize(normalized)
        if not tokens:
            return False

        if tokens[0] in self.VOICE_QUESTION_STARTERS:
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
        if not normalized_response.startswith(self.FALLBACK_PREFIXES):
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
