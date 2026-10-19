"""Spotify-specific local UI control; never sends keys to other applications."""
import json
import subprocess
import time
import urllib.request
from urllib.parse import urlparse
from websockets.sync.client import connect
from helpers.config import get_env


def mpris(method, *args):
    result = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.mpris.MediaPlayer2.spotify',
        '--object-path', '/org/mpris/MediaPlayer2', '--method', method, *args],
        capture_output=True, text=True, timeout=3)
    if result.returncode:
        raise RuntimeError('Spotify is not ready for playback control.')
    return result.stdout


def evaluate(expression):
    port = max(1024, min(65535, get_env('SPOTIFY_CONTROL_PORT', 9229, int)))
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=2) as response:
        pages = json.load(response)
    page = next(p for p in pages if p.get('type') == 'page' and
                urlparse(p.get('url', '')).hostname == 'xpui.app.spotify.com')
    endpoint = page['webSocketDebuggerUrl']
    if urlparse(endpoint).hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise RuntimeError('Spotify control endpoint must be local.')
    with connect(endpoint, open_timeout=2, close_timeout=1) as socket:
        socket.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate',
            'params': {'expression': expression, 'returnByValue': True}}))
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            message = json.loads(socket.recv(timeout=3))
            if message.get('id') == 1:
                return message.get('result', {}).get('result', {}).get('value')
    return None


def play_search(query, uri):
    mpris('org.mpris.MediaPlayer2.Player.OpenUri', uri)
    # Only act when the search box shows this request and the result has a
    # matching accessible play label. Unrelated current playback is not success.
    expression = '''(() => {
      const norm = s => (s || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim();
      const q = QUERY;
      const input = document.querySelector('input[data-testid="search-input"]') || document.querySelector('input[role="combobox"]');
      if (!input || norm(input.value) !== norm(q)) return null;
      const buttons = Array.from(document.querySelectorAll('main button[aria-label]'));
      const button = buttons.find(b => ['play '+norm(q), 'reproduzir '+norm(q), 'tocar '+norm(q)].includes(norm(b.getAttribute('aria-label'))));
      if (!button) return null;
      const label = button.getAttribute('aria-label'); button.click(); return label;
    })()'''.replace('QUERY', json.dumps(query))
    deadline = time.monotonic() + 12
    clicked = None
    while time.monotonic() < deadline:
        clicked = evaluate(expression)
        if clicked:
            break
        time.sleep(.35)
    if not clicked:
        return False
    while time.monotonic() < deadline + 4:
        status = mpris('org.freedesktop.DBus.Properties.Get', 'org.mpris.MediaPlayer2.Player', 'PlaybackStatus')
        metadata = mpris('org.freedesktop.DBus.Properties.Get', 'org.mpris.MediaPlayer2.Player', 'Metadata')
        words = [w for w in query.lower().split() if len(w) > 2]
        if "'Playing'" in status and words and all(w in metadata.lower() for w in words):
            return True
        time.sleep(.25)
    return False
