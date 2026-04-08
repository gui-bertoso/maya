import re
import shutil
import subprocess
import urllib.parse


class SpotifyAssistant:
    @staticmethod
    def _clean_request_tail(text):
        cleaned = (text or "").strip()
        cleaned = re.sub(r"[.!?,;:]+$", "", cleaned).strip()
        cleaned = re.sub(r"\s+(?:on|in|using|via)\s+spotify$", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+(?:no|na|pelo|via)\s+spotify$", "", cleaned, flags=re.IGNORECASE).strip()
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
            subprocess.Popen(command)
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
            r"^(?:open|start|launch)\s+spotify$",
            r"^(?:abre|abrir|inicia|iniciar)\s+spotify$",
        ]
        if any(re.match(pattern, stripped, flags=re.IGNORECASE) for pattern in direct_open_patterns):
            return {
                "mode": "app",
                "query": None,
                "spoken_query": None,
            }

        music_prefix = r"^(?:play|open|put on|start|toca|toque|bota|coloca)\s+"
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
            r"^(?:play|open)\s+(.+?)\s+on\s+spotify$",
            r"^open spotify and play\s+(.+)$",
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

        uri = self.build_search_uri(query)
        app_key = app_launcher.resolve_alias("spotify")
        if app_key and hasattr(app_launcher, "launch_with_target"):
            success, _ = app_launcher.launch_with_target(app_key, uri)
            if success:
                return True

        if self._launch_flatpak(uri):
            return True

        if hasattr(app_launcher, "launch_any"):
            success, _ = app_launcher.launch_any(uri)
            return success

        return False
