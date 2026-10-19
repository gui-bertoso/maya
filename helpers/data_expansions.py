import json
import re
import time
from pathlib import Path

from helpers.config import get_resource_path, get_runtime_path


CONTAINER_PATTERN = re.compile(r"^DataExpansion(\d+)\.(myde|json)$", re.IGNORECASE)
FORMAT_NAME = "maya-data-expansion"
FORMAT_VERSION = 1


class DataExpansionLoader:
    """Merge numbered command/response containers and hot-reload changed files."""

    def __init__(self, directory=None, refresh_interval=1.0):
        self.directory = Path(directory) if directory else get_runtime_path("data/expansions")
        self.refresh_interval = max(0.0, float(refresh_interval))
        self.command_aliases = {}
        self.responses = {}
        self.loaded_files = []
        self.errors = []
        self._fingerprint = None
        self._last_check = 0.0

    def _container_paths(self):
        if not self.directory.exists():
            return []
        numbered = []
        for path in self.directory.glob("DataExpansion*.*"):
            match = CONTAINER_PATTERN.match(path.name)
            if match:
                numbered.append((int(match.group(1)), path.name.lower(), path))
        return [item[2] for item in sorted(numbered)]

    def _current_fingerprint(self, paths):
        return tuple((str(path.resolve()), path.stat().st_mtime_ns, path.stat().st_size) for path in paths)

    @staticmethod
    def _merge(target, additions):
        for key, values in additions.items():
            if not isinstance(key, str) or not isinstance(values, list):
                continue
            bucket = target.setdefault(key, [])
            for value in values:
                if isinstance(value, str) and value.strip() and value not in bucket:
                    bucket.append(value)

    def refresh(self, force=False):
        now = time.monotonic()
        if not force and now - self._last_check < self.refresh_interval:
            return False
        self._last_check = now

        paths = self._container_paths()
        fingerprint = self._current_fingerprint(paths)
        if not force and fingerprint == self._fingerprint:
            return False

        commands = {}
        responses = {}
        loaded_files = []
        errors = []
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8") as file:
                    payload = json.load(file)
                if not isinstance(payload, dict):
                    raise ValueError("container root must be an object")
                if path.suffix.lower() == ".myde":
                    if payload.get("format") != FORMAT_NAME:
                        raise ValueError(f"format must be {FORMAT_NAME!r}")
                    if payload.get("format_version") != FORMAT_VERSION:
                        raise ValueError(f"unsupported format_version: {payload.get('format_version')!r}")
                self._merge(commands, payload.get("commands", {}))
                self._merge(responses, payload.get("responses", {}))
                loaded_files.append(path.name)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                errors.append(f"{path.name}: {error}")

        self.command_aliases = commands
        self.responses = responses
        self.loaded_files = loaded_files
        self.errors = errors
        self._fingerprint = fingerprint
        return True


def load_legacy_expansions():
    commands = {}
    responses = {}
    for relative_path, target in (
        ("data/command_aliases.json", commands),
        ("data/response_expansions.json", responses),
    ):
        path = get_resource_path(relative_path)
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            DataExpansionLoader._merge(target, payload)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return commands, responses
