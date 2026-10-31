"""Optional loopback-only llama.cpp process owned by Maya; text in, text out.

No tool definitions or executable output. Model weights are installed explicitly.
"""
import atexit
import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

from helpers.config import get_runtime_path, get_env
from helpers.dialogue_settings import values as dialogue_settings


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Local dialogue does not follow redirects')


class LocalDialogueRuntime:
    def __init__(self):
        self._lock = threading.RLock()
        self._process = None
        self._port = None
        self._signature = None
        self._key = secrets.token_urlsafe(32)
        self._retry_after = 0
        self.status = {'state': 'stopped', 'backend': 'Vulkan'}
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        atexit.register(self.close)

    def _request(self, route, payload=None, timeout=3):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
        request = urllib.request.Request(
            f'http://127.0.0.1:{self._port}{route}', data=data,
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self._key})
        with self._http.open(request, timeout=timeout) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError('Local model response too large')
            return json.loads(raw)

    def _start(self):
        settings = dialogue_settings()
        signature = tuple(settings[key] for key in ('LOCAL_DIALOGUE_CONTEXT', 'LOCAL_DIALOGUE_GPU_LAYERS',
                          'LOCAL_DIALOGUE_THREADS', 'LOCAL_DIALOGUE_IDLE_SECONDS'))
        if self._process is not None and self._process.poll() is None:
            if signature == self._signature:
                return
            self.close()
        self._signature = signature
        manifest = json.loads(get_runtime_path('.runtime/local-dialogue/install.json').read_text(encoding='utf-8'))
        binary = get_runtime_path(manifest['binary']).resolve()
        model = get_runtime_path(manifest['model']).resolve()
        if not binary.is_file() or not model.is_file():
            raise FileNotFoundError('Run scripts/install_local_dialogue.py first')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self._port = sock.getsockname()[1]
        env = os.environ.copy()
        env['LLAMA_API_KEY'] = self._key
        command = [str(binary), '--model', str(model), '--host', '127.0.0.1',
                   '--port', str(self._port), '--ctx-size', str(settings['LOCAL_DIALOGUE_CONTEXT']), '--parallel', '1',
                   '--n-gpu-layers', str(settings['LOCAL_DIALOGUE_GPU_LAYERS']),
                   '--device', 'Vulkan0' if settings['LOCAL_DIALOGUE_GPU_LAYERS'] else 'none', '--flash-attn', 'on',
                   '--cache-type-k', 'q8_0', '--cache-type-v', 'q8_0',
                   '--batch-size', '256', '--ubatch-size', '128', '--threads', str(settings['LOCAL_DIALOGUE_THREADS']),
                   '--jinja', '--reasoning', 'off', '--chat-template-kwargs', '{"enable_thinking":false}',
                   '--no-webui', '--sleep-idle-seconds', str(settings['LOCAL_DIALOGUE_IDLE_SECONDS']), '--log-disable']
        # Server logs can include prompts; keep them off disk and out of diagnostics.
        self._process = subprocess.Popen(command, cwd=binary.parent, env=env,
                                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, start_new_session=True)
        self.status = {'state': 'loading', 'backend': 'Vulkan' if settings['LOCAL_DIALOGUE_GPU_LAYERS'] else 'CPU', 'model': model.name}
        deadline = time.monotonic() + settings['LOCAL_DIALOGUE_STARTUP_TIMEOUT']
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError('Local server exited during startup')
            try:
                if self._request('/health', timeout=1).get('status') == 'ok':
                    self.status['state'] = 'ready'
                    return
            except (OSError, ValueError, urllib.error.URLError):
                pass
            time.sleep(.2)
        raise TimeoutError('Local model startup timed out')

    def generate(self, messages):
        with self._lock:
            if time.monotonic() < self._retry_after:
                return None
            started = time.monotonic()
            try:
                self._start()
                settings = dialogue_settings()
                result = self._request('/v1/chat/completions', {
                    'messages': messages, 'max_tokens': settings['LOCAL_DIALOGUE_MAX_TOKENS'],
                    'temperature': settings['LOCAL_DIALOGUE_TEMPERATURE'],
                    'top_p': settings['LOCAL_DIALOGUE_TOP_P'], 'top_k': 20, 'min_p': 0,
                    'repeat_penalty': 1.05, 'stream': False,
                    'chat_template_kwargs': {'enable_thinking': False},
                }, timeout=settings['LOCAL_DIALOGUE_TIMEOUT'])
                choice = result['choices'][0]
                message = choice['message']
                content = message.get('content')
                if message.get('tool_calls') or not isinstance(content, str) or not content.strip():
                    raise ValueError('Expected a textual model answer')
                # Never speak reasoning or incomplete generation.
                if '<think>' in content or '</think>' in content or choice.get('finish_reason') == 'length':
                    raise ValueError('Incomplete answer or reasoning in final content')
                self.status.update(state='ready', elapsed_seconds=round(time.monotonic() - started, 3),
                                   usage=result.get('usage', {}), timings=result.get('timings', {}))
                return content.strip()
            except (OSError, ValueError, KeyError, IndexError, TypeError, RuntimeError, urllib.error.URLError) as error:
                self.close()
                self._retry_after = time.monotonic() + 30
                self.status = {'state': 'fallback', 'backend': 'Vulkan', 'error_type': type(error).__name__}
                if str(get_env('DEBUG_MODE', 'false')).lower() == 'true':
                    print(f'[llm] fallback error={type(error).__name__}; retry in 30s', flush=True)
                return None

    def close(self):
        with self._lock:
            child, self._process = self._process, None
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=2)
            if self.status.get('state') != 'fallback':
                self.status['state'] = 'stopped'


_RUNTIME = None
_RUNTIME_LOCK = threading.Lock()


def runtime():
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = LocalDialogueRuntime()
        return _RUNTIME


def runtime_status():
    if _RUNTIME is None:
        return {'state': 'stopped', 'backend': 'Vulkan'}
    return {key: value for key, value in _RUNTIME.status.items()
            if key in {'state', 'backend', 'model', 'elapsed_seconds', 'error_type'}}


def release_runtime():
    if _RUNTIME is not None:
        _RUNTIME.close()
