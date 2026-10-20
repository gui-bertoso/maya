"""Local whisper.cpp bridge: a resident loopback server and bounded speech segments."""
import io
import json
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
import wave
from collections import deque
from pathlib import Path
from urllib.request import Request, urlopen

from helpers.config import get_resource_path, get_runtime_path
from input.voice import Voice, sd
from helpers.diagnostics import report_error


class WhisperServer:
    def __init__(self, binary, model, language='en', threads=6, use_gpu=True, prompt='', timeout=30):
        self.binary = Path(binary)
        self.model = Path(model)
        self.language = language
        self.threads = max(1, int(threads))
        self.use_gpu = use_gpu
        self.prompt = prompt
        self.timeout = max(1, float(timeout))
        self.process = None
        self.url = None
        self._stopped = threading.Event()

    def start(self):
        if not self.binary.is_file():
            raise FileNotFoundError(f'whisper-server not found: {self.binary}')
        if not self.model.is_file():
            raise FileNotFoundError(f'Whisper model not found: {self.model}')
        if self._stopped.is_set():
            raise RuntimeError('Whisper startup cancelled')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        command = [str(self.binary), '-m', str(self.model), '--host', '127.0.0.1',
                   '--port', str(port), '-t', str(self.threads), '-l', self.language, '-sns', '-nf']
        if not self.use_gpu:
            command.append('-ng')
        if sys.platform.startswith('linux'):
            # Set parent-death handling in a fresh Python child, avoiding unsafe
            # preexec_fn hooks in Maya's multithreaded process.
            owner_guard = (
                "import ctypes,os,signal,sys; parent=os.getppid(); "
                "ctypes.CDLL(None).prctl(1,signal.SIGTERM); "
                "sys.exit(1) if os.getppid()!=parent else None; "
                "os.execv(sys.argv[1],sys.argv[1:])"
            )
            command = [sys.executable, '-c', owner_guard, *command]
        log_path = get_runtime_path('logs/whisper-server.log')
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('ab') as log:
            self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        self.url = f'http://127.0.0.1:{port}'
        deadline = time.monotonic() + 90
        try:
            while not self._stopped.is_set() and time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f'whisper-server exited ({self.process.returncode}); see {log_path}')
                try:
                    with urlopen(self.url + '/health', timeout=1) as response:
                        if json.load(response).get('status') == 'ok':
                            return
                except (OSError, ValueError):
                    pass
                self._stopped.wait(.1)
            raise TimeoutError('Whisper startup cancelled or timed out; see logs/whisper-server.log')
        except Exception:
            self.stop()
            raise

    def transcribe(self, pcm, sample_rate=16000):
        if sample_rate != 16000:
            raise ValueError('Whisper requires 16 kHz capture')
        if not pcm or self._stopped.is_set():
            return ''
        wav = io.BytesIO()
        with wave.open(wav, 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(sample_rate)
            stream.writeframes(pcm)
        boundary = 'maya-' + uuid.uuid4().hex
        parts = []
        for name, value in [('response_format', 'json'), ('temperature', '0.0'),
                            ('temperature_inc', '0.0'), ('prompt', self.prompt)]:
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode() + wav.getvalue() + b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())
        request = Request(self.url + '/inference', data=b''.join(parts),
                          headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
        with urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read(1024 * 1024))
        text = result.get('text')
        if not isinstance(text, str):
            raise ValueError('Whisper returned an invalid transcription')
        return re.sub(r'\[[^\]]*\]|<\|[^|]*\|>', '', text).strip()

    def stop(self):
        self._stopped.set()
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)


class WhisperVoice(Voice):
    def __init__(self, binary, whisper_model, language='en', threads=6, use_gpu=True,
                 prompt='', can_capture=None, **kwargs):
        super().__init__(**kwargs)
        if self.sample_rate != 16000:
            raise ValueError('Set VOICE_SAMPLE_RATE=16000 for whisper.cpp')
        self.backend = WhisperServer(get_resource_path(binary), get_resource_path(whisper_model),
                                     language, threads, use_gpu, prompt)
        self.can_capture = can_capture or (lambda: True)
        self.segments = queue.Queue(maxsize=1)
        self.decoder_thread = None

    def start_background(self, on_final_text=None, on_partial_text=None, on_status_change=None):
        if not self.thread or not self.thread.is_alive():
            self.backend._stopped.clear()
        return super().start_background(on_final_text, on_partial_text, on_status_change)

    def _backend_available(self):
        if not self.backend.binary.is_file() or not self.backend.model.is_file():
            self.last_error = 'Whisper binary/model missing; see docs/whisper-cpp.md'
            report_error("voice_model", operation="voice.whisper.files", context={"engine":"whisper.cpp"})
            return False
        return True

    def load_voice(self, on_status_change=None):
        self.set_status('loading', on_status_change)
        try:
            self.backend.start()
            self.is_loaded = not self._stop_requested.is_set()
        except Exception as error:
            self.last_error = str(error)
            if not self._stop_requested.is_set():
                report_error("voice_server", error, operation="voice.whisper.start", context={"engine":"whisper.cpp"})
                self.set_status('error', on_status_change)

    def _decode_loop(self, on_final_text, on_status_change):
        while not self._stop_requested.is_set():
            try:
                pcm = self.segments.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                self.set_status('thinking', on_status_change)
                text = self.backend.transcribe(pcm, self.sample_rate)
                if not self._stop_requested.is_set():
                    self.set_status('ready', on_status_change)
                    if text and on_final_text:
                        on_final_text(text)
            except Exception as error:
                self.last_error = str(error)
                if not self._stop_requested.is_set():
                    report_error("voice_timeout" if isinstance(error,TimeoutError) else "voice_runtime", error,
                                 operation="voice.whisper.transcribe", context={"engine":"whisper.cpp"})
                    self.set_status('error', on_status_change)

    def _queue_segment(self, frames, speech_blocks):
        # Tiny clicks and silence must not reach a generative recognizer.
        if speech_blocks < 2:
            return False
        try:
            self.segments.put_nowait(b''.join(frames))
            return True
        except queue.Full:
            report_error("voice_backpressure", operation="voice.whisper.submit", notify=False)
            return False

    def _listen_loop(self, on_final_text=None, on_partial_text=None, on_status_change=None):
        self.load_voice(on_status_change)
        if not self.is_loaded or self._stop_requested.is_set():
            return
        self.decoder_thread = threading.Thread(target=self._decode_loop,
            args=(on_final_text, on_status_change), daemon=True, name='maya-whisper-decode')
        self.decoder_thread.start()
        self.is_listening = True
        frames, speech_blocks, silent_blocks = [], 0, 0
        preroll = deque(maxlen=2)
        max_blocks = max(1, int(15 * self.sample_rate / self.block_size))
        try:
            with sd.RawInputStream(samplerate=self.sample_rate, blocksize=self.block_size,
                                   dtype='int16', channels=1, callback=self.audio_callback):
                self.set_status('ready', on_status_change)
                while not self._stop_requested.is_set():
                    try:
                        data, has_speech = self.audio_queue.get(timeout=.2)
                    except queue.Empty:
                        continue
                    # Half duplex for now: do not transcribe Maya's own loudspeaker output.
                    if not self.can_capture():
                        frames, speech_blocks, silent_blocks = [], 0, 0
                        preroll.clear()
                        continue
                    if not frames:
                        if not has_speech:
                            preroll.append(data)
                            continue
                        frames = list(preroll)
                        preroll.clear()
                        self.set_status('hearing', on_status_change)
                    frames.append(data)
                    speech_blocks += int(has_speech)
                    silent_blocks = 0 if has_speech else silent_blocks + 1
                    if silent_blocks >= self.endpoint_silence_blocks or len(frames) >= max_blocks:
                        if not self._queue_segment(frames, speech_blocks):
                            self.set_status('busy' if speech_blocks >= 2 else 'ready', on_status_change)
                        frames, speech_blocks, silent_blocks = [], 0, 0
        except Exception as error:
            self.last_error = str(error)
            if not self._stop_requested.is_set():
                report_error("voice_runtime", error, operation="voice.whisper.capture", context={"engine":"whisper.cpp"})
                self.set_status('error', on_status_change)
        finally:
            self.is_listening = False
            self._stop_requested.set()
            self.backend.stop()
            if self.status != 'error':
                self.set_status('idle', on_status_change)

    def stop(self):
        super().stop()
        self.backend.stop()
        decoder = self.decoder_thread
        if decoder and decoder is not threading.current_thread():
            decoder.join(timeout=1)
        while not self.segments.empty():
            try:
                self.segments.get_nowait()
            except queue.Empty:
                break
