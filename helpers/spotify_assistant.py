import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse


class SpotifyAssistant:
    last_playback_confirmed = False
    last_error = ""
    WINDOWS_SEARCH_TIMEOUT = 12.0

    @staticmethod
    def _clean_request_tail(text):
        cleaned = (text or "").strip()
        cleaned = re.sub(r"[.!?,;:]+$", "", cleaned).strip()
        cleaned = re.sub(r"\s+(?:on|in|using|via)\s+(?:the\s+)?spotify$", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+(?:no|na|pelo|pela|via|em)\s+(?:o\s+|a\s+)?spotify$", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+(?:for me|please|pra mim|por favor)$", "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned

    @staticmethod
    def _extract_query(text, prefix_pattern):
        cleaned = SpotifyAssistant._clean_request_tail(text)
        cleaned = re.sub(prefix_pattern, "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^(?:a|an|the|some|my|uma|um|o|a|minha|meu)\s+", "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned

    @staticmethod
    def _launch_flatpak(target=None):
        flatpak_bin = shutil.which("flatpak")
        if not flatpak_bin:
            return False

        command = [flatpak_bin, "run", "com.spotify.Client"]
        if target:
            command.append(target)

        try:
            installed = subprocess.run([flatpak_bin, "info", "com.spotify.Client"], capture_output=True, timeout=3)
            if installed.returncode:
                return False
            subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def build_search_uri(self, query):
        encoded = urllib.parse.quote(query.strip())
        return f"spotify:search:{encoded}"

    def build_track_query(self, query):
        return query.strip()

    def build_playlist_query(self, query):
        clean = query.strip()
        if "playlist" in clean.lower():
            return clean
        return f"{clean} playlist"

    def parse_request(self, text):
        stripped = self._clean_request_tail(text)

        playlist_patterns = [
            r"^(?:play|open)\s+(?:a\s+)?(.+?)\s+playlist\s+on\s+spotify$",
            r"^(?:play|open)\s+(?:some\s+)?(.+?)\s+on\s+spotify\s+playlist$",
            r"^open spotify and play\s+(?:a\s+)?(.+?)\s+playlist$",
            r"^(?:play|open|put on|start|toca|toque|bota|coloca)\s+(.+?)\s+playlist$",
            r"^(?:play|open|put on|start|toca|toque|bota|coloca)\s+(?:a\s+|some\s+|uma\s+)?playlist\s+(?:of\s+|de\s+)?(.+)$",
            r"^(?:tocar|reproduz|reproduzir|abre|abrir)\s+(.+?)\s+playlist$",
            r"^(?:tocar|reproduz|reproduzir|abre|abrir)\s+(?:uma\s+)?playlist\s+(?:de\s+)?(.+)$",
        ]
        for pattern in playlist_patterns:
            match = re.match(pattern, stripped, flags=re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                if topic:
                    return {
                        "mode": "playlist",
                        "query": self.build_playlist_query(topic),
                        "spoken_query": topic,
                    }

        direct_open_patterns = [
            r"^(?:open|start|launch)\s+(?:the\s+)?spotify$",
            r"^(?:abre|abrir|inicia|iniciar)\s+(?:o\s+|a\s+)?spotify$",
        ]
        if any(re.match(pattern, stripped, flags=re.IGNORECASE) for pattern in direct_open_patterns):
            return {
                "mode": "app",
                "query": None,
                "spoken_query": None,
            }

        music_prefix = r"^(?:play|put on|toca|toque|tocar|bota|coloca|reproduz|reproduzir)\s+"
        if re.match(music_prefix, stripped, flags=re.IGNORECASE):
            topic = self._extract_query(stripped, music_prefix)
            if topic:
                topic = re.sub(r"\s+(?:song|music|track|musica|música)$", "", topic, flags=re.IGNORECASE).strip()
                if topic:
                    return {
                        "mode": "track",
                        "query": self.build_track_query(topic),
                        "spoken_query": topic,
                    }

        track_patterns = [
            r"^(?:play|open)\s+(.+?)\s+on\s+(?:the\s+)?spotify$",
            r"^open spotify and play\s+(.+)$",
            r"^(?:toca|toque|tocar|abre|abrir|reproduz|reproduzir)\s+(.+?)\s+(?:no|na|em)\s+(?:o\s+|a\s+)?spotify$",
            r"^abre\s+(?:o\s+|a\s+)?spotify\s+e\s+(?:toca|toque|tocar|reproduz|reproduzir)\s+(.+)$",
        ]
        for pattern in track_patterns:
            match = re.match(pattern, stripped, flags=re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                if topic:
                    return {
                        "mode": "track",
                        "query": self.build_track_query(topic),
                        "spoken_query": topic,
                    }

        return None

    def open_app(self, app_launcher):
        if not app_launcher:
            return self._launch_flatpak()

        app_key = app_launcher.resolve_alias("spotify")
        if not app_key:
            return self._launch_flatpak()

        success, _ = app_launcher.launch(app_key)
        return success or self._launch_flatpak()

    def open_search(self, app_launcher, query):
        if not app_launcher:
            return False

        self.last_playback_confirmed = False
        self.last_error = ""
        if sys.platform.startswith("linux"):
            from helpers.config import get_env
            from helpers.spotify_linux import mpris, play_search
            try:
                try:
                    mpris('org.freedesktop.DBus.Properties.Get', 'org.mpris.MediaPlayer2.Player', 'PlaybackStatus')
                except RuntimeError:
                    if not self.open_app(app_launcher):
                        return False
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            mpris('org.freedesktop.DBus.Properties.Get', 'org.mpris.MediaPlayer2.Player', 'PlaybackStatus')
                            break
                        except RuntimeError:
                            if time.monotonic() >= deadline:
                                return False
                            time.sleep(.25)
                uri = self.build_search_uri(query)
                mpris('org.mpris.MediaPlayer2.Player.OpenUri', uri)
                if get_env("SPOTIFY_UI_CONTROL", "true").lower() == "true":
                    try:
                        self.last_playback_confirmed = play_search(query, uri)
                    except Exception as error:
                        self.last_error = str(error)
                return True
            except Exception as error:
                self.last_error = str(error)
                return False

        uri = self.build_search_uri(query)
        app_key = app_launcher.resolve_alias("spotify")
        if app_key and hasattr(app_launcher, "launch_with_target"):
            success, _ = app_launcher.launch_with_target(app_key, uri)
            if success:
                if sys.platform.startswith("win"):
                    self._schedule_windows_playback(query, app_launcher, app_key)
                return True

        if self._launch_flatpak(uri):
            return True

        if hasattr(app_launcher, "launch_any"):
            success, _ = app_launcher.launch_any(uri)
            return success

        return False

    @staticmethod
    def _find_windows_spotify_window():
        """Return the visible Spotify HWND, if the desktop client is running."""
        if not sys.platform.startswith("win"):
            return None

        try:
            import psutil
            import win32gui
            import win32process
        except ImportError:
            return None

        found = []

        def callback(hwnd, _extra):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process_name = psutil.Process(pid).name().lower()
                if process_name in {"spotify.exe", "spotifywebhelper.exe"}:
                    title = win32gui.GetWindowText(hwnd).strip().lower()
                    if process_name == "spotify.exe" or "spotify" in title:
                        found.append(hwnd)
            except (OSError, psutil.Error):
                pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            return None
        return found[0] if found else None

    @staticmethod
    def _set_windows_clipboard(text):
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, str(text))
        finally:
            win32clipboard.CloseClipboard()

    @staticmethod
    def _press_windows_key(key, modifiers=()):
        import win32api
        import win32con

        virtual_keys = {
            "ctrl": win32con.VK_CONTROL,
            "enter": win32con.VK_RETURN,
            "tab": win32con.VK_TAB,
            "down": win32con.VK_DOWN,
        }
        key_code = virtual_keys[key] if key in virtual_keys else ord(key.upper())
        modifier_codes = [virtual_keys[item] for item in modifiers]
        for modifier in modifier_codes:
            win32api.keybd_event(modifier, 0, 0, 0)
        win32api.keybd_event(key_code, 0, 0, 0)
        win32api.keybd_event(key_code, 0, win32con.KEYEVENTF_KEYUP, 0)
        for modifier in reversed(modifier_codes):
            win32api.keybd_event(modifier, 0, win32con.KEYEVENTF_KEYUP, 0)

    def _play_search_on_windows(self, query, app_launcher, app_key):
        """Use Spotify's desktop search UI to play the first matching result."""
        deadline = time.time() + self.WINDOWS_SEARCH_TIMEOUT
        window_id = None
        while time.time() < deadline:
            window_id = self._find_windows_spotify_window()
            if window_id:
                break
            time.sleep(0.35)

        if not window_id:
            return False

        try:
            import win32gui

            win32gui.ShowWindow(window_id, 9)  # SW_RESTORE
            win32gui.SetForegroundWindow(window_id)
            time.sleep(0.25)
            self._set_windows_clipboard(query)
            self._press_windows_key("l", modifiers=("ctrl",))
            self._press_windows_key("v", modifiers=("ctrl",))
            self._press_windows_key("enter")
            time.sleep(1.35)

            # The search field keeps focus after loading. Move to the first
            # result and confirm it, which starts the requested track/playlist.
            self._press_windows_key("tab")
            self._press_windows_key("enter")
            return True
        except Exception:
            return False

    def _schedule_windows_playback(self, query, app_launcher, app_key):
        worker = threading.Thread(
            target=self._play_search_on_windows,
            args=(query, app_launcher, app_key),
            name="maya-spotify-playback",
            daemon=True,
        )
        worker.start()
