import json
import os
import glob
import getpass
import re
import subprocess
import sys
import shlex
import shutil
import time
from pathlib import Path

from helpers.config import get_path

APPS_PATH = get_path("APPS_PATH", "data/apps.json")


class AppLauncher:
    DISCOVERY_TIME_BUDGET_SECONDS = 1.5
    DISCOVERY_MAX_DIRECTORIES = 2500

    def __init__(self, apps_path=APPS_PATH):
        self.apps_path = apps_path
        self.system_username = self.detect_system_username()
        self.platform_key = self.detect_platform_key()
        self.apps = self.load_apps()
        self._discovery_cache = {}

    @staticmethod
    def detect_system_username():
        return os.getenv("USERNAME") or getpass.getuser()

    @staticmethod
    def detect_platform_key():
        if sys.platform.startswith("win"):
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        return "linux"

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

    def get_subapps(self, app_key):
        config = self.apps.get(app_key, {})
        subapps = config.get("subapps")
        return subapps if isinstance(subapps, dict) else {}

    def resolve_alias(self, alias):
        if not alias:
            return None

        alias_map = self.get_alias_map()
        normalized = alias.strip().lower()

        normalized = re.sub(r"^(?:o|a|os|as)\s+", "", normalized).strip()
        normalized = re.sub(r"\s+(?:app|aplicativo|programa)$", "", normalized).strip()

        if normalized in alias_map:
            return alias_map[normalized]

        return None

    def available_aliases(self):
        return sorted(self.get_alias_map().keys())

    def get_subapp_alias_map(self, app_key):
        alias_map = {}

        for subapp_key, config in self.get_subapps(app_key).items():
            aliases = config.get("aliases", [])
            for alias in aliases:
                alias_map[alias.strip().lower()] = subapp_key

        return alias_map

    def resolve_subapp_alias(self, app_key, alias):
        if not alias:
            return None

        alias_map = self.get_subapp_alias_map(app_key)
        normalized = alias.strip().lower()
        return alias_map.get(normalized)

    def get_subapp_display_name(self, app_key, subapp_key):
        config = self.get_subapps(app_key).get(subapp_key, {})
        return config.get("display_name", subapp_key)

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

    def get_platform_value(self, config, key):
        if not isinstance(config, dict):
            return None

        platform_specific_key = f"{key}_{self.platform_key}"
        if platform_specific_key in config:
            return config.get(platform_specific_key)

        value = config.get(key)
        if isinstance(value, dict):
            return (
                value.get(self.platform_key)
                or value.get("default")
                or value.get("windows")
                or value.get("linux")
                or value.get("macos")
            )

        return value

    def resolve_command(self, command):
        if isinstance(command, list):
            return [self.resolve_command(part) for part in command]

        expanded = self.expand_command_value(command)

        if isinstance(expanded, str) and self.has_wildcards(expanded):
            return self.resolve_pattern_path(expanded)

        return expanded

    @staticmethod
    def _command_exists(command):
        if not command:
            return False
        return subprocess.run(
            ["sh", "-lc", f"command -v {subprocess.list2cmdline([str(command)])} >/dev/null 2>&1"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode == 0

    def _resolve_platform_command(self, config):
        command = self.get_platform_value(config, "command")
        if not command:
            return None

        if isinstance(command, list) and command and all(isinstance(item, str) for item in command):
            return self.resolve_command(command)

        if isinstance(command, str):
            return self.resolve_command(command)

        if isinstance(command, tuple):
            return self.resolve_command(list(command))

        return command

    def _open_target(self, target):
        if sys.platform.startswith("win"):
            os.startfile(target)
            return

        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, target])

    def launch(self, app_key):
        config = self.apps.get(app_key)
        if not config:
            return False, "unknown_app"

        command = self.get_platform_value(config, "command")
        if not command:
            return False, "missing_command"

        resolved_command = self._resolve_platform_command(config)

        try:
            if isinstance(resolved_command, list):
                subprocess.Popen(resolved_command)
            else:
                target = str(resolved_command)
                if os.path.exists(target) or target.startswith(("http://", "https://")):
                    self._open_target(target)
                else:
                    subprocess.Popen([target])
        except Exception:
            return False, "launch_failed"

        return True, None

    def launch_with_target(self, app_key, target):
        config = self.apps.get(app_key)
        if not config:
            return False, "unknown_app"

        command = self.get_platform_value(config, "command")
        if not command:
            return False, "missing_command"

        resolved_command = self._resolve_platform_command(config)

        try:
            if isinstance(resolved_command, list):
                subprocess.Popen(resolved_command + [target])
            else:
                subprocess.Popen([str(resolved_command), target])
        except Exception:
            return False, "launch_failed"

        return True, None

    def launch_subapp(self, app_key, subapp_alias):
        config = self.apps.get(app_key)
        if not config:
            return False, "unknown_app"

        subapp_key = self.resolve_subapp_alias(app_key, subapp_alias)
        if not subapp_key:
            if app_key == "steam":
                return self.launch_discovered_app(subapp_alias, prefer_steam=True)
            return False, "unknown_subapp"

        subapp_config = self.get_subapps(app_key).get(subapp_key, {})
        target = self.get_platform_value(subapp_config, "target")
        if not target:
            return False, "missing_target"

        resolved_target = self.resolve_command(target)
        return self.launch_with_target(app_key, resolved_target)

    def launch_any(self, raw_target):
        if not raw_target or not raw_target.strip():
            return False, "missing_command"

        try:
            target = raw_target.strip()
            if target.startswith(("http://", "https://")) or os.path.exists(os.path.expanduser(target)):
                self._open_target(os.path.expanduser(target))
            elif self.platform_key in {"windows", "linux"}:
                launched, _ = self.launch_discovered_app(target)
                if not launched:
                    if self.platform_key == "windows":
                        subprocess.Popen(["cmd", "/c", "start", "", target])
                    else:
                        subprocess.Popen([target])
            else:
                subprocess.Popen([target])
        except Exception:
            return False, "launch_failed"

        return True, None

    @staticmethod
    def _normalize_lookup_name(value):
        normalized = re.sub(r"\.(?:exe|lnk|url)$", "", str(value or ""), flags=re.IGNORECASE)
        normalized = normalized.lower().strip()
        normalized = re.sub(
            r"^(?:the|o|a|os|as|app|aplicativo|programa|game|jogo)\s+",
            "",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\s+(?:app|aplicativo|programa|game|jogo|na steam|no steam|in steam|on steam)$",
            "",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return " ".join(normalized.split())

    def _score_discovered_candidate(self, query, candidate_name, full_path, prefer_steam=False):
        normalized_query = self._normalize_lookup_name(query)
        normalized_name = self._normalize_lookup_name(candidate_name)
        normalized_path = self._normalize_lookup_name(full_path)
        if not normalized_query or not normalized_name:
            return -1

        score = 0
        if normalized_query == normalized_name:
            score += 120
        elif normalized_query in normalized_name:
            score += 80
        elif normalized_name in normalized_query:
            score += 65

        query_tokens = set(normalized_query.split())
        name_tokens = set(normalized_name.split())
        overlap = len(query_tokens & name_tokens)
        score += overlap * 18

        if normalized_query and normalized_query in normalized_path:
            score += 20

        suffix_bonus = 10 if full_path.lower().endswith(".exe") else 0
        score += suffix_bonus

        if prefer_steam and "steam" in full_path.lower():
            score += 35

        return score

    @staticmethod
    def _is_executable_file(path):
        return os.path.isfile(path) and os.access(path, os.X_OK)

    @staticmethod
    def _parse_desktop_exec(exec_value):
        if not exec_value:
            return None
        try:
            parts = shlex.split(exec_value)
        except ValueError:
            return None

        filtered = [part for part in parts if not re.fullmatch(r"%[fFuUdDnNickvm]", part)]
        return filtered or None

    def _read_desktop_entry(self, desktop_path):
        try:
            content = Path(desktop_path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

        in_entry = False
        data = {}
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("["):
                in_entry = line.lower() == "[desktop entry]"
                continue
            if not in_entry or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()

        if data.get("NoDisplay", "").lower() == "true":
            return None
        if data.get("Hidden", "").lower() == "true":
            return None

        return data or None

    @staticmethod
    def _iter_existing_paths(paths):
        seen = set()
        for raw_path in paths:
            if not raw_path:
                continue
            expanded = os.path.expandvars(os.path.expanduser(str(raw_path)))
            if expanded in seen or not os.path.exists(expanded):
                continue
            seen.add(expanded)
            yield expanded

    @staticmethod
    def _read_windows_registry_value(root, subkey, value_name):
        if not sys.platform.startswith("win"):
            return None

        try:
            import winreg
        except ImportError:
            return None

        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value
        except OSError:
            return None

    def _get_windows_steam_registry_paths(self):
        if not sys.platform.startswith("win"):
            return []

        try:
            import winreg
        except ImportError:
            return []

        candidates = [
            self._read_windows_registry_value(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            self._read_windows_registry_value(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamExe"),
            self._read_windows_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            self._read_windows_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ]

        normalized = []
        for candidate in candidates:
            if not candidate:
                continue
            steam_path = str(candidate).strip().strip('"')
            if steam_path.lower().endswith("steam.exe"):
                steam_path = os.path.dirname(steam_path)
            normalized.append(steam_path)
        return normalized

    def _get_steam_library_paths(self):
        roots = [
            os.getenv("STEAM_PATH", ""),
            os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Steam"),
            os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Steam"),
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Steam"),
            os.path.join(os.getenv("USERPROFILE", ""), "scoop", "apps", "steam", "current"),
            *self._get_windows_steam_registry_paths(),
        ]
        libraries = []

        for steam_root in self._iter_existing_paths(roots):
            libraries.append(steam_root)
            library_file = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
            if not os.path.exists(library_file):
                continue
            try:
                content = Path(library_file).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for match in re.finditer(r'"path"\s+"([^"]+)"', content):
                library_path = match.group(1).replace("\\\\", "\\")
                if os.path.exists(library_path):
                    libraries.append(library_path)

        deduped = []
        seen = set()
        for item in libraries:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(item)
        return deduped

    def _get_linux_steam_library_paths(self):
        roots = [
            "~/.steam/steam",
            "~/.local/share/Steam",
            "~/.var/app/com.valvesoftware.Steam/.local/share/Steam",
        ]
        libraries = []

        for steam_root in self._iter_existing_paths(roots):
            libraries.append(steam_root)
            library_file = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
            if not os.path.exists(library_file):
                continue
            try:
                content = Path(library_file).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for match in re.finditer(r'"path"\s+"([^"]+)"', content):
                library_path = match.group(1).replace("\\\\", "\\")
                if os.path.exists(library_path):
                    libraries.append(library_path)

        deduped = []
        seen = set()
        for item in libraries:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(item)
        return deduped

    def _find_steam_manifest_target(self, query):
        normalized_query = self._normalize_lookup_name(query)
        if not normalized_query:
            return None

        if self.platform_key == "windows":
            libraries = self._get_steam_library_paths()
        elif self.platform_key == "linux":
            libraries = self._get_linux_steam_library_paths()
        else:
            libraries = []

        best = None
        for library in libraries:
            steamapps_dir = os.path.join(library, "steamapps")
            if not os.path.isdir(steamapps_dir):
                continue

            for manifest in glob.glob(os.path.join(steamapps_dir, "appmanifest_*.acf")):
                try:
                    content = Path(manifest).read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

                appid_match = re.search(r'"appid"\s+"(\d+)"', content)
                name_match = re.search(r'"name"\s+"([^"]+)"', content)
                if not appid_match or not name_match:
                    continue

                app_name = name_match.group(1)
                score = self._score_discovered_candidate(
                    normalized_query,
                    app_name,
                    manifest,
                    prefer_steam=True,
                )
                if score < 80:
                    continue

                candidate = (score, f"steam://rungameid/{appid_match.group(1)}")
                if not best or candidate[0] > best[0]:
                    best = candidate

        return best[1] if best else None

    def _get_windows_search_roots(self, prefer_steam=False):
        steam_roots = self._get_steam_library_paths()
        default_roots = [
            os.path.join(os.getenv("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.getenv("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.getenv("USERPROFILE", ""), "Desktop"),
            os.getenv("ProgramFiles", r"C:\Program Files"),
            os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs"),
            os.getenv("LOCALAPPDATA", ""),
            r"C:\Games",
            r"D:\Games",
        ]
        if prefer_steam:
            return list(self._iter_existing_paths(steam_roots + default_roots))
        return list(self._iter_existing_paths(default_roots + steam_roots))

    def _get_linux_search_roots(self, prefer_steam=False):
        steam_roots = self._get_linux_steam_library_paths()
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        xdg_data_dirs = [path for path in os.getenv("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if path]
        app_dirs = [
            os.path.join(xdg_data_home, "applications"),
            os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
            "/var/lib/flatpak/exports/share/applications",
        ]
        app_dirs.extend(os.path.join(path, "applications") for path in xdg_data_dirs)

        default_roots = [
            *app_dirs,
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Applications"),
            os.path.expanduser("~/.local/bin"),
            os.path.expanduser("~/bin"),
            "/usr/local/bin",
            "/usr/bin",
            "/opt",
            os.path.expanduser("~/Games"),
            os.path.expanduser("~/.local/share/applications"),
        ]

        if prefer_steam:
            return list(self._iter_existing_paths(steam_roots + default_roots))
        return list(self._iter_existing_paths(default_roots + steam_roots))

    def _discovery_deadline(self):
        return time.monotonic() + self.DISCOVERY_TIME_BUDGET_SECONDS

    @staticmethod
    def _deadline_exceeded(deadline):
        return deadline is not None and time.monotonic() >= deadline

    def _should_stop_discovery(self, deadline, visited_directories):
        if visited_directories >= self.DISCOVERY_MAX_DIRECTORIES:
            return True
        return self._deadline_exceeded(deadline)

    def _discover_windows_candidates(self, query, prefer_steam=False):
        normalized_query = self._normalize_lookup_name(query)
        if not normalized_query:
            return []

        cache_key = (normalized_query, bool(prefer_steam))
        if cache_key in self._discovery_cache:
            return list(self._discovery_cache[cache_key])

        roots = self._get_windows_search_roots(prefer_steam=prefer_steam)
        candidates = []
        seen_paths = set()
        allowed_suffixes = {".exe", ".lnk", ".url"}
        deadline = self._discovery_deadline()
        visited_directories = 0
        found_exact_match = False

        for root in roots:
            if self._should_stop_discovery(deadline, visited_directories):
                break
            for current_root, dirnames, filenames in os.walk(root):
                visited_directories += 1
                if self._should_stop_discovery(deadline, visited_directories):
                    break

                dirnames[:] = [
                    item for item in dirnames
                    if item.lower() not in {"cache", "logs", "tmp", "temp", "__pycache__"}
                ]

                folder_name = os.path.basename(current_root)
                folder_score = self._score_discovered_candidate(
                    normalized_query,
                    folder_name,
                    current_root,
                    prefer_steam=prefer_steam,
                )
                if folder_score >= 80:
                    candidates.append((folder_score, current_root, folder_name))
                    if folder_score >= 120:
                        found_exact_match = True

                for filename in filenames:
                    if os.path.splitext(filename)[1].lower() not in allowed_suffixes:
                        continue
                    full_path = os.path.join(current_root, filename)
                    if full_path.lower() in seen_paths:
                        continue

                    score = self._score_discovered_candidate(
                        normalized_query,
                        filename,
                        full_path,
                        prefer_steam=prefer_steam,
                    )
                    if score < 80:
                        continue

                    seen_paths.add(full_path.lower())
                    candidates.append((score, full_path, filename))
                    if score >= 120:
                        found_exact_match = True

                if found_exact_match and candidates:
                    break

            if found_exact_match and candidates:
                break

        candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1].lower()))
        self._discovery_cache[cache_key] = candidates[:20]
        return list(self._discovery_cache[cache_key])

    def _discover_linux_candidates(self, query, prefer_steam=False):
        normalized_query = self._normalize_lookup_name(query)
        if not normalized_query:
            return []

        cache_key = ("linux", normalized_query, bool(prefer_steam))
        if cache_key in self._discovery_cache:
            return list(self._discovery_cache[cache_key])

        candidates = []
        seen = set()
        steam_target = self._find_steam_manifest_target(query) if prefer_steam else None
        if steam_target:
            candidates.append((200, steam_target, "steam-manifest"))

        path_match = shutil.which(query.strip())
        if path_match:
            score = self._score_discovered_candidate(normalized_query, os.path.basename(path_match), path_match, prefer_steam)
            candidates.append((max(score, 100), path_match, os.path.basename(path_match)))

        deadline = self._discovery_deadline()
        visited_directories = 0
        found_exact_match = any(score >= 120 for score, _, _ in candidates)

        for root in self._get_linux_search_roots(prefer_steam=prefer_steam):
            if self._should_stop_discovery(deadline, visited_directories):
                break
            for current_root, dirnames, filenames in os.walk(root):
                visited_directories += 1
                if self._should_stop_discovery(deadline, visited_directories):
                    break

                dirnames[:] = [
                    item for item in dirnames
                    if item.lower() not in {"cache", "logs", "tmp", "temp", "__pycache__", ".git", "shadercache"}
                ]

                for filename in filenames:
                    full_path = os.path.join(current_root, filename)
                    lowered_path = full_path.lower()
                    if lowered_path in seen:
                        continue

                    ext = os.path.splitext(filename)[1].lower()
                    allowed = ext == ".desktop" or ext == ".appimage" or self._is_executable_file(full_path)
                    if not allowed:
                        continue

                    display_name = filename
                    if ext == ".desktop":
                        entry = self._read_desktop_entry(full_path)
                        if not entry:
                            continue
                        display_name = entry.get("Name") or entry.get("Name[pt_BR]") or filename

                    score = self._score_discovered_candidate(
                        normalized_query,
                        display_name,
                        full_path,
                        prefer_steam=prefer_steam,
                    )
                    if score < 80:
                        continue

                    seen.add(lowered_path)
                    candidates.append((score, full_path, display_name))
                    if score >= 120:
                        found_exact_match = True

                if found_exact_match and candidates:
                    break

            if found_exact_match and candidates:
                break

        candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1].lower()))
        self._discovery_cache[cache_key] = candidates[:20]
        return list(self._discovery_cache[cache_key])

    def find_installed_app_target(self, query, prefer_steam=False):
        if self.platform_key in {"windows", "linux"}:
            steam_target = self._find_steam_manifest_target(query)
            if steam_target:
                return steam_target

        if self.platform_key == "windows":
            candidates = self._discover_windows_candidates(query, prefer_steam=prefer_steam)
        elif self.platform_key == "linux":
            candidates = self._discover_linux_candidates(query, prefer_steam=prefer_steam)
        else:
            return None

        if not candidates:
            return None
        return candidates[0][1]

    def launch_discovered_app(self, query, prefer_steam=False):
        target = self.find_installed_app_target(query, prefer_steam=prefer_steam)
        if not target:
            return False, "not_found"

        try:
            if self.platform_key == "windows":
                os.startfile(target)
            elif target.startswith(("http://", "https://", "steam://")):
                self._open_target(target)
            elif target.endswith(".desktop"):
                entry = self._read_desktop_entry(target)
                command = self._parse_desktop_exec(entry.get("Exec")) if entry else None
                if command:
                    executable = command[0]
                    resolved = shutil.which(executable) or executable
                    subprocess.Popen([resolved] + command[1:])
                else:
                    self._open_target(target)
            elif os.path.isdir(target):
                self._open_target(target)
            else:
                subprocess.Popen([target])
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
        configured = self.get_platform_value(config, "process_names") or []
        process_names = []

        for item in configured:
            name = self._strip_exe_name(item)
            if name:
                process_names.append(name)

        if process_names:
            return process_names

        command = self.get_platform_value(config, "command")
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
                if sys.platform.startswith("win"):
                    result = subprocess.run(
                        ["taskkill", "/IM", f"{process_name}.exe", "/F"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                else:
                    result = subprocess.run(
                        ["pkill", "-f", process_name],
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
