import queue
import time
import threading
import numpy as np
from helpers.config import get_env
from helpers.diagnostics import report_error

try:
    import sounddevice as sd
    _SOUNDDEVICE_IMPORT_ERROR = None
except (ImportError, OSError) as error:
    sd = None
    _SOUNDDEVICE_IMPORT_ERROR = error

def get_rms(audio_data):
    audio_np = np.frombuffer(audio_data, dtype=np.int16)
    rms = np.sqrt(np.mean(audio_np.astype(np.float32) ** 2))
    return rms
class ClapDetector:
    def __init__(self, sample_rate=16000, channels=1, threshold=1800, cooldown=0.20, double_clap_window=0.80):
        self.sample_rate = sample_rate
        self.channels = channels
        self.threshold = threshold
        self.cooldown = cooldown
        self.double_clap_window = double_clap_window

        self.audio_queue = queue.Queue(maxsize=16)
        self._stop_requested = threading.Event()
        self.thread = None
        self.is_running = False

        self.last_clap_time = 0.0
        self.first_clap_time = 0.0
        self.debug_counter = 0
        self.clap_count = 0

        self.DEBUG_MODE = get_env("DEBUG_MODE", "false").lower() == "true"
        self.UI_MODE = get_env("UI_MODE", "maya")
        self.LANGUAGE = get_env("LANGUAGE", "en")
        self.last_error = None

    def has_input_device(self):
        if sd is None:
            self.last_error = str(_SOUNDDEVICE_IMPORT_ERROR) if _SOUNDDEVICE_IMPORT_ERROR else "sounddevice is unavailable"
            return False

        try:
            devices = sd.query_devices()
        except Exception as error:
            report_error("microphone_device", error, operation="clap_detector.has_input_device", notify=False)
            self.last_error = str(error)
            return False

        for device in devices:
            if device.get("max_input_channels", 0) > 0:
                return True

        self.last_error = "no input audio device was found"
        return False

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            if self.DEBUG_MODE:
                print("clap audio status:", status)

        try:
            self.audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            pass

    def detect_clap(self, audio_data):
        audio_np = np.frombuffer(audio_data, dtype=np.int16)

        if len(audio_np) == 0:
            return False, 0

        rms = np.sqrt(np.mean(audio_np.astype(np.float32) ** 2))
        self.debug_counter += 1
        if self.debug_counter % 10 == 0:
            if self.DEBUG_MODE:
                print("rms:", int(rms))
        return rms > self.threshold, rms

    def process_audio(self, on_double_clap=None, on_clap=None):
        if self._stop_requested.is_set():
            return
        self.is_running = True

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=1024,
                dtype="int16",
                channels=self.channels,
                callback=self.audio_callback
            ):
                if self.DEBUG_MODE:
                    print("clap detector listening...")

                while self.is_running and not self._stop_requested.is_set():
                    try:
                        audio_data = self.audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    is_clap, rms = self.detect_clap(audio_data)
                    now = time.time()

                    if not is_clap:
                        continue

                    if now - self.last_clap_time < self.cooldown:
                        continue

                    self.last_clap_time = now

                    if on_clap:
                        on_clap(rms)

                    if self.clap_count == 0:
                        self.clap_count = 1
                        self.first_clap_time = now

                    elif self.clap_count == 1:
                        if now - self.first_clap_time <= self.double_clap_window:
                            self.clap_count = 0
                            self.first_clap_time = 0.0

                            if self.DEBUG_MODE:
                                print("double clap detected")
                            if on_double_clap:
                                on_double_clap()
                        else:
                            self.clap_count = 1
                            self.first_clap_time = now

                    if self.clap_count == 1 and (now - self.first_clap_time > self.double_clap_window):
                        self.clap_count = 0
                        self.first_clap_time = 0.0

        except Exception as error:
            self.last_error = str(error)
            report_error("voice_runtime", error, operation="voice.clap.capture")

        finally:
            self.is_running = False
            if self.DEBUG_MODE:
                print("clap detector stopped")

    def start(self, on_double_clap=None, on_clap=None):
        if self.thread and self.thread.is_alive():
            return not self._stop_requested.is_set()

        if not self.has_input_device():
            report_error("microphone_device", operation="voice.clap.start", notify=False)
            return False

        self._stop_requested.clear()
        self.last_error = None
        self.thread = threading.Thread(
            target=self.process_audio,
            kwargs={
                "on_double_clap": on_double_clap,
                "on_clap": on_clap
            },
            daemon=True
        )
        self.thread.start()
        return True

    def stop(self):
        self._stop_requested.set()
        self.is_running = False
