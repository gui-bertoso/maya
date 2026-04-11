import os
import sys
import time
from dataclasses import dataclass

import psutil

from helpers.app_launcher import AppLauncher
from helpers.spotify_assistant import SpotifyAssistant


@dataclass(frozen=True)
class ExternalWindow:
    window_id: int
    pid: int | None
    title: str
    app_name: str
    process_name: str


class DevWorkspaceOrchestrator:
    def __init__(self, own_pid=None, own_caption="maya"):
        self.own_pid = own_pid or os.getpid()
        self.own_caption = (own_caption or "").strip().lower()
        self.app_launcher = AppLauncher()
        self.spotify_assistant = SpotifyAssistant()
        self.display = None
        self.root = None
        self.X = None
        self.protocol = None
        self._atoms = {}
        self.win32 = None

        if sys.platform.startswith("win"):
            self._init_windows_backend()
            return

        if os.name != "posix" or "linux" not in os.sys.platform:
            return

        if not os.getenv("DISPLAY"):
            return

        try:
            from Xlib import X, display, protocol
        except Exception:
            return

        try:
            self.display = display.Display()
            self.root = self.display.screen().root
            self.X = X
            self.protocol = protocol
        except Exception:
            self.display = None
            self.root = None
            self.X = None
            self.protocol = None

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
        except Exception:
            self.win32 = None

    @property
    def available(self):
        if self.win32 is not None:
            return True
        return self.display is not None and self.root is not None and self.X is not None and self.protocol is not None

    def _atom(self, name):
        atom = self._atoms.get(name)
        if atom is None and self.display is not None:
            atom = self.display.intern_atom(name, only_if_exists=False)
            self._atoms[name] = atom
        return atom

    def _decode_property(self, value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore").replace("\x00", " ").strip()
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            return " ".join(str(item) for item in value if item not in (None, "")).strip()
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
            return ""
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

    def _get_client_window_ids(self):
        for name in ("_NET_CLIENT_LIST_STACKING", "_NET_CLIENT_LIST"):
            try:
                prop = self.root.get_full_property(self._atom(name), self.X.AnyPropertyType)
                if prop is not None and getattr(prop, "value", None):
                    return [int(window_id) for window_id in prop.value]
            except Exception:
                continue
        return []

    def list_windows(self):
        if not self.available:
            return []

        if self.win32 is not None:
            snapshots = []
            seen_ids = set()
            win32gui = self.win32["gui"]
            win32process = self.win32["process"]

            def callback(hwnd, _extra):
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

                if self.own_caption and title.strip().lower().startswith(self.own_caption):
                    return True

                process_name = ""
                if pid:
                    try:
                        process_name = psutil.Process(pid).name().strip().lower()
                    except Exception:
                        process_name = ""

                app_name = process_name
                if not app_name:
                    try:
                        app_name = win32gui.GetClassName(hwnd).strip().lower()
                    except Exception:
                        app_name = ""

                if hwnd in seen_ids:
                    return True

                snapshots.append(
                    ExternalWindow(
                        window_id=hwnd,
                        pid=pid,
                        title=title,
                        app_name=app_name,
                        process_name=process_name,
                    )
                )
                seen_ids.add(hwnd)
                return True

            try:
                win32gui.EnumWindows(callback, None)
            except Exception:
                return []

            return snapshots

        snapshots = []
        seen_ids = set()
        for window_id in reversed(self._get_client_window_ids()):
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

            if self.own_caption and title.strip().lower().startswith(self.own_caption):
                continue

            process_name = ""
            if pid:
                try:
                    process_name = psutil.Process(pid).name().strip().lower()
                except Exception:
                    process_name = ""

            snapshots.append(
                ExternalWindow(
                    window_id=window_id,
                    pid=pid,
                    title=title,
                    app_name=(self._read_window_app_name(window) or "").strip().lower(),
                    process_name=process_name,
                )
            )
            seen_ids.add(window_id)

        return snapshots

    def _matches_window(self, window_snapshot, process_names, terms):
        process_names = {item.lower() for item in process_names if item}
        terms = [item.lower() for item in terms if item]
        haystacks = [
            (window_snapshot.process_name or "").lower(),
            (window_snapshot.app_name or "").lower(),
            (window_snapshot.title or "").lower(),
        ]

        if any(name and haystacks[0] == name for name in process_names):
            return True
        if any(name and name in haystacks[1] for name in process_names):
            return True
        if any(term and any(term in hay for hay in haystacks) for term in terms):
            return True
        return False

    def wait_for_window(self, process_names, terms, timeout=18.0):
        deadline = time.time() + max(1.0, timeout)
        while time.time() < deadline:
            for snapshot in self.list_windows():
                if self._matches_window(snapshot, process_names, terms):
                    return snapshot
            time.sleep(0.35)
        return None

    def _send_client_message(self, target_window, message_type, data):
        event = self.protocol.event.ClientMessage(
            window=target_window,
            client_type=self._atom(message_type),
            data=(32, data),
        )
        self.root.send_event(
            event,
            event_mask=self.X.SubstructureRedirectMask | self.X.SubstructureNotifyMask,
        )

    def _set_maximized(self, window_id, enabled):
        if not self.available:
            return

        try:
            target_window = self.display.create_resource_object("window", int(window_id))
            action = 1 if enabled else 0
            self._send_client_message(
                target_window,
                "_NET_WM_STATE",
                [
                    action,
                    self._atom("_NET_WM_STATE_MAXIMIZED_VERT"),
                    self._atom("_NET_WM_STATE_MAXIMIZED_HORZ"),
                    1,
                    0,
                ],
            )
            self.display.sync()
        except Exception:
            return

    def move_resize_window(self, window_id, x, y, width, height):
        if not self.available:
            return False

        if self.win32 is not None:
            try:
                win32gui = self.win32["gui"]
                win32con = self.win32["con"]
                target_id = int(window_id)
                win32gui.ShowWindow(target_id, win32con.SW_RESTORE)
                win32gui.MoveWindow(target_id, int(x), int(y), int(width), int(height), True)
                return True
            except Exception:
                return False

        try:
            target_window = self.display.create_resource_object("window", int(window_id))
            self._set_maximized(window_id, False)
            flags = (1 << 8) | (1 << 9) | (1 << 10) | (1 << 11)
            self._send_client_message(
                target_window,
                "_NET_MOVERESIZE_WINDOW",
                [flags, int(x), int(y), int(width), int(height)],
            )
            target_window.configure(x=int(x), y=int(y), width=int(width), height=int(height), border_width=0)
            target_window.map()
            target_window.raise_window()
            self.display.sync()
            return True
        except Exception:
            return False

    def activate_window(self, window_id):
        if not self.available:
            return False
        if self.win32 is not None:
            try:
                win32gui = self.win32["gui"]
                win32con = self.win32["con"]
                target_id = int(window_id)
                win32gui.ShowWindow(target_id, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_id)
                return True
            except Exception:
                return False
        try:
            target_window = self.display.create_resource_object("window", int(window_id))
            self._send_client_message(
                target_window,
                "_NET_ACTIVE_WINDOW",
                [2, self.X.CurrentTime, 0, 0, 0],
            )
            target_window.map()
            target_window.raise_window()
            self.display.sync()
            return True
        except Exception:
            return False

    def position_window_on_screen(self, window_snapshot, screen, mode):
        x = int(screen["x"])
        y = int(screen["y"])
        width = int(screen["width"])
        height = int(screen["height"])

        if mode == "left_half":
            return self.move_resize_window(window_snapshot.window_id, x, y, max(120, width // 2), height)
        if mode == "right_half":
            half_width = max(120, width // 2)
            return self.move_resize_window(window_snapshot.window_id, x + half_width, y, width - half_width, height)
        return self.move_resize_window(window_snapshot.window_id, x, y, width, height)

    def run_default_dev_workspace(self, screens, spotify_query="pique anos 80"):
        result = {
            "firefox": False,
            "spotify": False,
            "layout": False,
            "reason": "",
        }

        firefox_key = self.app_launcher.resolve_alias("firefox")
        spotify_key = self.app_launcher.resolve_alias("spotify")

        if firefox_key:
            launched, _reason = self.app_launcher.launch(firefox_key)
            result["firefox"] = launched
        if spotify_key:
            result["spotify"] = self.spotify_assistant.open_search(self.app_launcher, spotify_query or "pique anos 80")

        if not self.available:
            result["reason"] = "x11_window_control_unavailable"
            return result

        safe_screens = list(screens or [])
        if not safe_screens:
            result["reason"] = "no_screens"
            return result

        secondary_screen = safe_screens[1] if len(safe_screens) > 1 else safe_screens[0]

        firefox_window = self.wait_for_window(
            self.app_launcher.get_process_names(firefox_key) if firefox_key else [],
            ["firefox", "mozilla firefox"],
        )
        spotify_window = self.wait_for_window(
            self.app_launcher.get_process_names(spotify_key) if spotify_key else [],
            ["spotify"],
        )

        positioned = []
        if firefox_window:
            positioned.append(self.position_window_on_screen(firefox_window, secondary_screen, "left_half"))
        if spotify_window:
            positioned.append(self.position_window_on_screen(spotify_window, secondary_screen, "right_half"))

        result["layout"] = any(positioned)
        if firefox_window:
            self.activate_window(firefox_window.window_id)
        if not result["layout"] and not any([firefox_window, spotify_window]):
            result["reason"] = "no_matching_windows_found"
        return result
