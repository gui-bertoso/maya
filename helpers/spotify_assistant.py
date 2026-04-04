import re
import urllib.parse


class SpotifyAssistant:
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
        stripped = text.strip()

        playlist_patterns = [
            r"^(?:play|open)\s+(?:a\s+)?(.+?)\s+playlist\s+on\s+spotify$",
            r"^(?:play|open)\s+(?:some\s+)?(.+?)\s+on\s+spotify\s+playlist$",
            r"^open spotify and play\s+(?:a\s+)?(.+?)\s+playlist$",
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

        if re.match(r"^(?:open|start|launch)\s+spotify$", stripped, flags=re.IGNORECASE):
            return {
                "mode": "app",
                "query": None,
                "spoken_query": None,
            }

        return None

    def open_app(self, app_launcher):
        if not app_launcher:
            return False

        app_key = app_launcher.resolve_alias("spotify")
        if not app_key:
            return False

        success, _ = app_launcher.launch(app_key)
        return success

    def open_search(self, app_launcher, query):
        if not app_launcher:
            return False

        uri = self.build_search_uri(query)
        app_key = app_launcher.resolve_alias("spotify")
        if app_key and hasattr(app_launcher, "launch_with_target"):
            success, _ = app_launcher.launch_with_target(app_key, uri)
            if success:
                return True

        if hasattr(app_launcher, "launch_any"):
            success, _ = app_launcher.launch_any(uri)
            return success

        return False
