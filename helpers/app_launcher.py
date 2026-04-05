import json
import os
import glob
import getpass
import subprocess

from helpers.config import get_path

APPS_PATH = get_path("APPS_PATH", "data/apps.json")


class AppLauncher:
    def __init__(self, apps_path=APPS_PATH):
        self.apps_path = apps_path
        self.system_username = self.detect_system_username()
        self.apps = self.load_apps()

    @staticmethod
    def detect_system_username():
        return os.getenv("USERNAME") or getpass.getuser()

    def load_apps(self):
        with open(self.apps_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def get_alias_map(self):
        alias_map = {}

        for app_key, config in self.apps.items():
            aliases = config.get("aliases", [])
            for alias in aliases:
                alias_map[alias.strip().lower()] = app_key

        return alias_map

    def get_display_name(self, app_key):
        config = self.apps.get(app_key, {})
        return config.get("display_name", app_key)

    def resolve_alias(self, alias):
        if not alias:
            return None

        alias_map = self.get_alias_map()
        normalized = alias.strip().lower()

        if normalized in alias_map:
            return alias_map[normalized]

        return None

    def available_aliases(self):
        return sorted(self.get_alias_map().keys())

    def expand_command_value(self, value):
        if not isinstance(value, str):
            return value

        expanded = value.replace("{username}", self.system_username)
        expanded = os.path.expandvars(expanded)
        expanded = os.path.expanduser(expanded)
        return expanded

    @staticmethod
    def has_wildcards(value):
        return any(char in value for char in ["*", "?", "["])

    def resolve_pattern_path(self, pattern):
        matches = glob.glob(pattern)
        if not matches:
            return pattern

        existing_matches = [match for match in matches if os.path.exists(match)]
        if not existing_matches:
            return pattern

        existing_matches.sort(key=lambda item: (os.path.getmtime(item), item.lower()), reverse=True)
        return existing_matches[0]

    def resolve_command(self, command):
        if isinstance(command, list):
            return [self.resolve_command(part) for part in command]

        expanded = self.expand_command_value(command)

        if isinstance(expanded, str) and self.has_wildcards(expanded):
            return self.resolve_pattern_path(expanded)

        return expanded

    def launch(self, app_key):
        config = self.apps.get(app_key)
        if not config:
            return False, "unknown_app"

        command = config.get("command")
        if not command:
            return False, "missing_command"

        resolved_command = self.resolve_command(command)

        try:
            if isinstance(resolved_command, list):
                subprocess.Popen(resolved_command)
            else:
                target = str(resolved_command)
                if os.path.exists(target) or target.startswith(("http://", "https://")):
                    os.startfile(target)
                else:
                    subprocess.Popen(["cmd", "/c", "start", "", target])
        except Exception:
            return False, "launch_failed"

        return True, None

    def launch_with_target(self, app_key, target):
        config = self.apps.get(app_key)
        if not config:
            return False, "unknown_app"

        command = config.get("command")
        if not command:
            return False, "missing_command"

        resolved_command = self.resolve_command(command)

        try:
            if isinstance(resolved_command, list):
                subprocess.Popen(resolved_command + [target])
            else:
                subprocess.Popen([str(resolved_command), target])
        except Exception:
            return False, "launch_failed"

        return True, None

    def launch_any(self, raw_target):
        if not raw_target or not raw_target.strip():
            return False, "missing_command"

        try:
            subprocess.Popen(["cmd", "/c", "start", "", raw_target.strip()])
        except Exception:
            return False, "launch_failed"

        return True, None

    @staticmethod
    def _strip_exe_name(value):
        if not value:
            return None
        name = os.path.basename(str(value)).strip().strip('"')
        if not name:
            return None
        if name.lower().endswith(".exe"):
            name = name[:-4]
        return name or None

    def get_process_names(self, app_key):
        config = self.apps.get(app_key, {})
        configured = config.get("process_names", [])
        process_names = []

        for item in configured:
            name = self._strip_exe_name(item)
            if name:
                process_names.append(name)

        if process_names:
            return process_names

        command = config.get("command")
        resolved_command = self.resolve_command(command) if command else None

        if isinstance(resolved_command, list) and resolved_command:
            inferred = self._strip_exe_name(resolved_command[0])
            return [inferred] if inferred else []

        inferred = self._strip_exe_name(resolved_command)
        return [inferred] if inferred else []

    def close(self, app_key):
        config = self.apps.get(app_key)
        if not config:
            return False, "unknown_app"

        process_names = self.get_process_names(app_key)
        if not process_names:
            return False, "missing_process_name"

        closed_any = False
        for process_name in process_names:
            try:
                result = subprocess.run(
                    ["taskkill", "/IM", f"{process_name}.exe", "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception:
                return False, "close_failed"

            if result.returncode == 0:
                closed_any = True

        if closed_any:
            return True, None

        return False, "not_running"
