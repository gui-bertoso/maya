import json
import os
import subprocess
from dataclasses import dataclass
import sys


@dataclass(frozen=True)
class WindowSnapshot:
    window_id: str
    title: str
    app_name: str
    is_active: bool = False


class WindowShowcaseBackend:
    def __init__(self, own_pid=None, own_caption="maya"):
        self.own_pid = own_pid or os.getpid()
        self.own_caption = (own_caption or "").strip().lower()
        self.available = False
        self.reason = ""
        self.display = None
        self.root = None
        self.X = None
        self.protocol = None
        self._atoms = {}
        self.backend_name = ""
        self.win32 = None

        if sys.platform.startswith("win") and self._init_windows_backend():
            return

        if not sys_platform_linux():
            self.reason = "window showcase is unavailable on this session."
            return

        if self._init_hyprland_backend():
            return

        if not os.getenv("DISPLAY") and self._init_kwin_backend():
            return

        if not os.getenv("DISPLAY"):
            self.reason = self._wayland_reason()
            return

        try:
            from Xlib import X, display, protocol
        except Exception as error:
            self.reason = f"python-xlib is not available: {error}"
            return

        try:
            self.display = display.Display()
            self.root = self.display.screen().root
            self.X = X
            self.protocol = protocol
            self.backend_name = "x11"
            self.available = True
        except Exception as error:
            self.reason = f"could not connect to the X11 display: {error}"

    def update_own_caption(self, caption):
        self.own_caption = (caption or "").strip().lower()

    def _init_windows_backend(self):
        try:
            import win32con
            import win32gui
            import win32process

            self.win32 = {
                "con": win32con,
                "gui": win32gui,
                "process": win32process,
            }
            self.backend_name = "windows"
            self.available = True
            return True
        except Exception as error:
            self.reason = f"pywin32 is not available: {error}"
            return False

    def _wayland_reason(self):
        desktop = os.getenv("XDG_CURRENT_DESKTOP", "").strip() or os.getenv("DESKTOP_SESSION", "").strip()
        desktop_lower = desktop.lower()
        if "cosmic" in desktop_lower:
            return "window showcase cannot control COSMIC windows yet because COSMIC does not expose a stable window-control CLI like Hyprland."
        if "kde" in desktop_lower or "plasma" in desktop_lower:
            return "window showcase needs X11 metadata or KWin DBus access on KDE Plasma."
        if os.getenv("XDG_SESSION_TYPE", "").strip().lower() == "wayland":
            return "window showcase needs X11 metadata or a supported Wayland compositor such as Hyprland."
        return "window showcase needs an X11 display."

    def _init_hyprland_backend(self):
        desktop = os.getenv("XDG_CURRENT_DESKTOP", "").strip() or os.getenv("DESKTOP_SESSION", "").strip()
        desktop_lower = desktop.lower()
        hypr_signature = os.getenv("HYPRLAND_INSTANCE_SIGNATURE", "").strip()
        is_hyprland_session = bool(hypr_signature) or "hyprland" in desktop_lower
        if not is_hyprland_session:
            return False

        if not command_exists("hyprctl"):
            self.reason = "Hyprland session detected, but the `hyprctl` command is not available."
            return False

        self.backend_name = "hyprland"
        self.available = True
        return True

    def _init_kwin_backend(self):
        desktop = os.getenv("XDG_CURRENT_DESKTOP", "").strip() or os.getenv("DESKTOP_SESSION", "").strip()
        desktop_lower = desktop.lower()
        if "kde" not in desktop_lower and "plasma" not in desktop_lower:
            return False

        try:
            import dbus
        except Exception as error:
            self.reason = f"KDE Plasma session detected, but python-dbus is not available: {error}"
            return False

        try:
            self.kwin_dbus = dbus.SessionBus()
            self.kwin_windows_runner = dbus.Interface(
                self.kwin_dbus.get_object("org.kde.KWin", "/WindowsRunner"),
                "org.kde.krunner1",
            )
            self.backend_name = "kwin"
            self.available = True
            return True
        except Exception as error:
            self.reason = f"could not talk to KWin through DBus: {error}"
            return False

    @staticmethod
    def _infer_app_name_from_title(title):
        normalized = str(title or "").strip()
        if not normalized:
            return "window"

        for separator in (" — ", " - ", " – ", " | ", " :: ", ": "):
            if separator in normalized:
                parts = [part.strip() for part in normalized.split(separator) if part.strip()]
                if parts:
                    return parts[-1]
        return normalized

    def _list_windows_windows(self, limit):
        if not self.win32:
            return [], self.reason or "windows backend is unavailable."

        win32gui = self.win32["gui"]
        win32process = self.win32["process"]
        foreground_hwnd = win32gui.GetForegroundWindow()
        snapshots = []
        seen_ids = set()

        def callback(hwnd, _extra):
            if len(snapshots) >= max(1, limit):
                return False

            if not win32gui.IsWindowVisible(hwnd):
                return True

            if win32gui.GetWindow(hwnd, self.win32["con"].GW_OWNER):
                return True

            title = (win32gui.GetWindowText(hwnd) or "").strip()
            if not title:
                return True

            try:
                _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                pid = None

            if pid == self.own_pid:
                return True

            normalized_title = title.lower()
            if self.own_caption and normalized_title.startswith(self.own_caption):
                return True

            if hwnd in seen_ids:
                return True

            app_name = ""
            if pid:
                try:
                    import psutil
                    app_name = psutil.Process(pid).name()
                except Exception:
                    app_name = ""

            if not app_name:
                try:
                    app_name = win32gui.GetClassName(hwnd)
                except Exception:
                    app_name = ""

            snapshots.append(
                WindowSnapshot(
                    window_id=str(hwnd),
                    title=title,
                    app_name=(app_name or self._infer_app_name_from_title(title)).strip(),
                    is_active=hwnd == foreground_hwnd,
                )
            )
            seen_ids.add(hwnd)
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as error:
            return [], f"could not enumerate Windows desktop windows: {error}"

        if not snapshots:
            return [], "i could not find viewable app windows to show right now."

        snapshots.sort(key=lambda item: (not item.is_active, item.app_name.lower(), item.title.lower()))
        return snapshots[:limit], ""

    def _list_kwin_windows(self, limit):
        try:
            matches = self.kwin_windows_runner.Match("windows")
        except Exception as error:
            self.reason = f"could not list KDE windows through DBus: {error}"
            return [], self.reason

        snapshots = []
        seen_ids = set()

        for index, match in enumerate(matches):
            if not isinstance(match, (list, tuple)) or len(match) < 2:
                continue

            window_id = str(match[0] or "").strip()
            title = str(match[1] or "").strip()
            if not window_id or not title or window_id in seen_ids:
                continue

            normalized_title = title.lower()
            if self.own_caption and normalized_title.startswith(self.own_caption):
                continue

            snapshots.append(
                WindowSnapshot(
                    window_id=window_id,
                    title=title,
                    app_name=self._infer_app_name_from_title(title),
                    is_active=index == 0,
                )
            )
            seen_ids.add(window_id)

            if len(snapshots) >= max(1, limit):
                break

        if not snapshots:
            return [], "i could not find KDE windows to show right now."

        return snapshots, ""

    def _run_hyprctl_json(self, *args):
        try:
            result = subprocess.run(
                ["hyprctl", "-j", *args],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.available = False
            self.reason = "the `hyprctl` command is not available anymore."
            return None
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or "").strip()
            self.reason = stderr or "could not talk to Hyprland through `hyprctl`."
            return None

        try:
            return json.loads(result.stdout or "null")
        except json.JSONDecodeError:
            self.reason = "Hyprland returned invalid JSON for the window showcase request."
            return None

    def _list_hyprland_windows(self, limit):
        clients = self._run_hyprctl_json("clients")
        if clients is None:
            return [], self.reason

        active_window = self._run_hyprctl_json("activewindow") or {}
        active_address = str(active_window.get("address") or "").strip().lower()
        snapshots = []
        seen_ids = set()

        for client in clients:
            if not isinstance(client, dict):
                continue

            window_id = str(client.get("address") or "").strip()
            if not window_id or window_id in seen_ids:
                continue

            if client.get("hidden") or client.get("minimized") or client.get("floating") is False and client.get("size") == [0, 0]:
                continue

            if not client.get("mapped", True):
                continue

            title = str(client.get("title") or "").strip()
            if not title:
                continue

            pid = client.get("pid")
            if pid == self.own_pid:
                continue

            normalized_title = title.lower()
            if self.own_caption and normalized_title == self.own_caption:
                continue

            app_name = str(client.get("class") or client.get("initialClass") or client.get("initialTitle") or "window").strip()
            snapshots.append(
                WindowSnapshot(
                    window_id=window_id,
                    title=title,
                    app_name=app_name or "window",
                    is_active=window_id.lower() == active_address,
                )
            )
            seen_ids.add(window_id)

        snapshots.sort(key=lambda item: (not item.is_active, item.app_name.lower(), item.title.lower()))
        if limit > 0:
            snapshots = snapshots[:limit]

        if not snapshots:
            return [], "i could not find mapped Hyprland windows to show right now."

        return snapshots, ""

    def _atom(self, name):
        atom = self._atoms.get(name)
        if atom is None and self.display is not None:
            atom = self.display.intern_atom(name, only_if_exists=False)
            self._atoms[name] = atom
        return atom

    @staticmethod
    def _decode_property(value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore").replace("\x00", " ").strip()
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            joined = " ".join(str(item) for item in value if item not in (None, ""))
            return joined.strip()
        return str(value).strip()

    def _read_text_property(self, window, name):
        try:
            prop = window.get_full_property(self._atom(name), 0)
            if prop is not None:
                return self._decode_property(prop.value)
        except Exception:
            return ""
        return ""

    def _read_window_pid(self, window):
        try:
            prop = window.get_full_property(self._atom("_NET_WM_PID"), self.X.AnyPropertyType)
            if prop is not None and getattr(prop, "value", None):
                return int(prop.value[0])
        except Exception:
            return None
        return None

    def _read_window_title(self, window):
        title = self._read_text_property(window, "_NET_WM_NAME")
        if title:
            return title

        try:
            wm_name = window.get_wm_name()
            if wm_name:
                return self._decode_property(wm_name)
        except Exception:
            pass

        return ""

    def _read_window_app_name(self, window):
        try:
            wm_class = window.get_wm_class()
            if wm_class:
                if isinstance(wm_class, (list, tuple)):
                    return next((part for part in reversed(wm_class) if part), "") or ""
                return self._decode_property(wm_class)
        except Exception:
            return ""
        return ""

    def _is_window_viewable(self, window):
        try:
            attributes = window.get_attributes()
            return attributes.map_state == self.X.IsViewable
        except Exception:
            return False

    def _get_active_window_id(self):
        try:
            prop = self.root.get_full_property(self._atom("_NET_ACTIVE_WINDOW"), self.X.AnyPropertyType)
            if prop is not None and getattr(prop, "value", None):
                return int(prop.value[0])
        except Exception:
            return None
        return None

    def _get_client_window_ids(self):
        property_names = ("_NET_CLIENT_LIST_STACKING", "_NET_CLIENT_LIST")
        for name in property_names:
            try:
                prop = self.root.get_full_property(self._atom(name), self.X.AnyPropertyType)
                if prop is not None and getattr(prop, "value", None):
                    return [int(window_id) for window_id in prop.value]
            except Exception:
                continue
        return []

    def list_windows(self, limit=10):
        if not self.available:
            return [], self.reason

        if self.backend_name == "windows":
            return self._list_windows_windows(limit)
        if self.backend_name == "hyprland":
            return self._list_hyprland_windows(limit)
        if self.backend_name == "kwin":
            return self._list_kwin_windows(limit)

        window_ids = self._get_client_window_ids()
        if not window_ids:
            return [], "no desktop windows were found on this X11 session."

        active_window_id = self._get_active_window_id()
        snapshots = []
        seen_ids = set()

        for window_id in reversed(window_ids):
            if window_id in seen_ids:
                continue

            try:
                window = self.display.create_resource_object("window", window_id)
            except Exception:
                continue

            if not self._is_window_viewable(window):
                continue

            title = self._read_window_title(window)
            if not title:
                continue

            pid = self._read_window_pid(window)
            if pid == self.own_pid:
                continue

            normalized_title = title.strip().lower()
            if self.own_caption and normalized_title == self.own_caption:
                continue

            snapshots.append(
                WindowSnapshot(
                    window_id=str(window_id),
                    title=title,
                    app_name=self._read_window_app_name(window) or "window",
                    is_active=window_id == active_window_id,
                )
            )
            seen_ids.add(window_id)

            if len(snapshots) >= max(1, limit):
                break

        if not snapshots:
            return [], "i could not find viewable app windows to show right now."

        return snapshots, ""

    def activate_window(self, window_id):
        if not self.available:
            return False, self.reason

        if not window_id:
            return False, "no window was selected."

        if self.backend_name == "windows":
            try:
                win32gui = self.win32["gui"]
                win32con = self.win32["con"]
                target_id = int(str(window_id), 0)
                win32gui.ShowWindow(target_id, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_id)
                return True, ""
            except Exception as error:
                return False, f"could not focus the selected window: {error}"

        if self.backend_name == "hyprland":
            target_id = str(window_id).strip()
            try:
                subprocess.run(
                    ["hyprctl", "dispatch", "focuswindow", f"address:{target_id}"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return True, ""
            except FileNotFoundError:
                self.available = False
                self.reason = "the `hyprctl` command is not available anymore."
                return False, self.reason
            except subprocess.CalledProcessError as error:
                stderr = (error.stderr or "").strip()
                return False, stderr or "could not focus the selected Hyprland window."

        if self.backend_name == "kwin":
            target_id = str(window_id).strip()
            try:
                self.kwin_windows_runner.Run(target_id, "")
                return True, ""
            except Exception as error:
                return False, f"could not focus the selected KDE window: {error}"

        try:
            target_window = self.display.create_resource_object("window", int(window_id))
            event = self.protocol.event.ClientMessage(
                window=target_window,
                client_type=self._atom("_NET_ACTIVE_WINDOW"),
                data=(32, [2, self.X.CurrentTime, 0, 0, 0]),
            )
            self.root.send_event(
                event,
                event_mask=self.X.SubstructureRedirectMask | self.X.SubstructureNotifyMask,
            )
            target_window.map()
            target_window.raise_window()
            self.display.sync()
            return True, ""
        except Exception as error:
            return False, f"could not focus the selected window: {error}"

    def minimize_window(self, window_id):
        if not self.available or not window_id:
            return False

        if self.backend_name == "windows":
            try:
                target_id = int(str(window_id), 0)
                self.win32["gui"].ShowWindow(target_id, self.win32["con"].SW_MINIMIZE)
                return True
            except Exception:
                return False

        if self.backend_name in {"hyprland", "kwin"}:
            return False

        try:
            target_window = self.display.create_resource_object("window", int(window_id))
            target_window.iconify()
            self.display.sync()
            return True
        except Exception:
            return False

    def restore_window(self, window_id):
        if not self.available or not window_id:
            return False

        if self.backend_name == "windows":
            try:
                target_id = int(str(window_id), 0)
                self.win32["gui"].ShowWindow(target_id, self.win32["con"].SW_RESTORE)
                return True
            except Exception:
                return False

        if self.backend_name == "hyprland":
            return False

        if self.backend_name == "kwin":
            success, _message = self.activate_window(window_id)
            return bool(success)

        try:
            target_window = self.display.create_resource_object("window", int(window_id))
            target_window.map()
            self.display.sync()
            return True
        except Exception:
            return False


def sys_platform_linux():
    return os.name == "posix" and "linux" in os.sys.platform


def command_exists(name):
    for path in os.getenv("PATH", "").split(os.pathsep):
        candidate = os.path.join(path, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return True
    return False
