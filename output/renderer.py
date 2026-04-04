import math
import sys

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QRegion
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLineEdit, QWidget

from helpers.config import get_env


def _apply_windows_overlay_style(widget):
    try:
        import ctypes

        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi

        GWL_STYLE = -16
        GWL_EXSTYLE = -20
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_MINIMIZE = 0x20000000
        WS_MAXIMIZEBOX = 0x00010000
        WS_SYSMENU = 0x00080000
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_LAYERED = 0x00080000

        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~WS_CAPTION
        style &= ~WS_THICKFRAME
        style &= ~WS_MINIMIZE
        style &= ~WS_MAXIMIZEBOX
        style &= ~WS_SYSMENU
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)

        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style &= ~WS_EX_APPWINDOW
        ex_style |= WS_EX_TOOLWINDOW
        ex_style |= WS_EX_LAYERED
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_DISABLED = 1
        DWMWA_BORDER_COLOR = 34
        DWMWA_CAPTION_COLOR = 35
        DWMWA_TEXT_COLOR = 36
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_DONOTROUND = 1
        DWM_COLOR_NONE = 0xFFFFFFFE

        value = ctypes.c_int(DWMNCRP_DISABLED)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_NCRENDERING_POLICY, ctypes.byref(value), ctypes.sizeof(value))

        border = ctypes.c_uint(DWM_COLOR_NONE)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border), ctypes.sizeof(border))
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(border), ctypes.sizeof(border))
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(border), ctypes.sizeof(border))

        backdrop = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop))

        corners = ctypes.c_int(DWMWCP_DONOTROUND)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(corners), ctypes.sizeof(corners))

        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass


class MayaRing:
    def __init__(self, width, height, radius=72, thickness=18):
        self.width = width
        self.height = height
        self.center_x = width / 2.0
        self.center_y = height / 2.0
        self.default_radius = radius
        self.default_thickness = thickness
        self.base_radius = radius
        self.base_thickness = thickness

        self.time = 0.0
        self.energy = 0.0
        self.target_energy = 2.0
        self.state = "idle"
        self.state_timer = 0.0
        self.state_color = QColor("#62ff8f")
        self.core_color = QColor("#ffffff")
        self.background_fill = QColor(0, 0, 0, 0)

    def resize(self, width, height):
        self.width = width
        self.height = height
        self.center_x = width / 2.0
        self.center_y = height / 2.0

    def set_scale(self, scale_factor):
        self.base_radius = self.default_radius * scale_factor
        self.base_thickness = max(2, self.default_thickness * scale_factor)

    def set_state(self, state, duration=0.0):
        self.state = state
        self.state_timer = duration

        if state == "idle":
            self.target_energy = 1.8
            self.state_color = QColor("#d8dee6")
            self.core_color = QColor("#ffffff")
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "ready":
            self.target_energy = 4.0
            self.state_color = QColor("#62ff8f")
            self.core_color = QColor("#ffffff")
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "hearing":
            self.target_energy = 14.0
            self.state_color = QColor("#ffd75e")
            self.core_color = QColor("#ffffff")
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "speaking":
            self.target_energy = 9.0
            self.state_color = QColor("#9ed0ff")
            self.core_color = QColor("#ffffff")
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "error":
            self.target_energy = 8.0
            self.state_color = QColor("#ff6b6b")
            self.core_color = QColor("#ffffff")
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "wake":
            self.target_energy = 22.0
            self.state_color = QColor("#62ff8f")
            self.core_color = QColor("#ffffff")
            self.background_fill = QColor(0, 0, 0, 0)
        else:
            self.target_energy = 3.0
            self.state_color = QColor("#dcdcdc")
            self.core_color = QColor("#ffffff")
            self.background_fill = QColor(0, 0, 0, 0)

    def update(self, dt):
        self.time += dt
        self.energy += (self.target_energy - self.energy) * min(dt * 7.0, 1.0)

        if self.state_timer > 0.0:
            self.state_timer -= dt
            if self.state_timer <= 0.0 and self.state in ("wake", "speaking"):
                self.set_state("ready")

    def _wave_radius(self, offset=0.0, scale=1.0):
        pulse = math.sin(self.time * 2.4 + offset) * (self.energy * 0.7 * scale)
        shimmer = math.sin(self.time * 1.3 + offset * 2.0) * (self.energy * 0.35 * scale)
        return self.base_radius + pulse + shimmer + offset

    @staticmethod
    def _mix(first, second, ratio):
        ratio = max(0.0, min(1.0, ratio))
        return QColor(
            int(first.red() + (second.red() - first.red()) * ratio),
            int(first.green() + (second.green() - first.green()) * ratio),
            int(first.blue() + (second.blue() - first.blue()) * ratio),
            int(first.alpha() + (second.alpha() - first.alpha()) * ratio),
        )

    def _ellipse_rect(self, radius):
        return QRect(
            int(self.center_x - radius),
            int(self.center_y - radius),
            int(radius * 2),
            int(radius * 2),
        )

    def draw(self, painter):
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.setPen(Qt.NoPen)
        painter.setBrush(self.background_fill)
        main_radius = self._wave_radius(0, 1.0)
        painter.drawEllipse(self._ellipse_rect(main_radius + self.base_thickness))

        outer_pen = QPen(self.state_color, 5.5)
        outer_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(outer_pen)
        painter.drawEllipse(self._ellipse_rect(self._wave_radius(18, 1.16)))

        main_pen = QPen(self.core_color, self.base_thickness)
        main_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(main_pen)
        painter.drawEllipse(self._ellipse_rect(main_radius))

        inner_pen = QPen(self.state_color, 4)
        inner_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(inner_pen)
        painter.drawEllipse(self._ellipse_rect(self._wave_radius(-11, 0.78)))


class OverlayWidget(QWidget):
    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.resize(renderer.window_size_x, renderer.window_size_y)
        self._update_mask()

    def _update_mask(self):
        self.setMask(QRegion(self.rect(), QRegion.Ellipse))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_mask()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self.renderer.ring.resize(self.width(), self.height())
        self.renderer.ring.draw(painter)


class QuickInputWidget(QWidget):
    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.resize(renderer.quick_input_width, renderer.quick_input_height)

        container = QFrame(self)
        container.setObjectName("quickInputCard")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(18, 14, 18, 14)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Talk to Maya...")
        self.entry.returnPressed.connect(self.submit_text)
        self.entry.textEdited.connect(lambda _text: self.renderer.handle_quick_input_keypress())
        self.entry.installEventFilter(self)
        layout.addWidget(self.entry)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(container)

        self.setStyleSheet(
            """
            QFrame#quickInputCard {
                background: rgba(7, 11, 18, 235);
                border: 1px solid rgba(120, 190, 255, 90);
                border-radius: 22px;
            }
            QLineEdit {
                background: transparent;
                border: none;
                color: rgb(239, 247, 255);
                font-size: 16px;
                selection-background-color: rgba(116, 184, 255, 120);
            }
            QLineEdit::placeholder {
                color: rgba(220, 235, 255, 120);
            }
            """
        )
        self.hide()

    def eventFilter(self, _obj, event):
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key_Escape:
            self.renderer.hide_quick_input()
            return True
        return False

    def submit_text(self):
        submitted_text = self.entry.text().strip()
        if submitted_text:
            if submitted_text == "exit":
                self.renderer.app.quit()
                return
            self.renderer.submit_input_callback(submitted_text)
        self.entry.clear()
        self.renderer.hide_quick_input()


class Renderer:
    def __init__(self, events, submit_input_callback, periodic_callback=None, keep_awake_callback=None):
        self.events = events
        self.submit_input_callback = submit_input_callback
        self.periodic_callback = periodic_callback
        self.keep_awake_callback = keep_awake_callback

        self.window_size_x = get_env("WINDOW_WIDTH", 260, int)
        self.window_size_y = get_env("WINDOW_HEIGHT", 260, int)
        self.base_window_size_x = self.window_size_x
        self.base_window_size_y = self.window_size_y
        self.window_caption = get_env("WINDOW_CAPTION", "maya")
        self.window_margin = get_env("WINDOW_MARGIN", 32, int)
        self.quick_input_width = get_env("QUICK_INPUT_WIDTH", 420, int)
        self.quick_input_height = get_env("QUICK_INPUT_HEIGHT", 92, int)
        self.scale_factor = 1.0
        self.initial_position = get_env("INITIAL_POSITION", "top_right")
        self.initial_monitor = max(1, get_env("INITIAL_MONITOR", 2, int))
        self.initial_scale = get_env("INITIAL_SCALE", 0.5, float)

        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.voice_status = "idle"
        self.response_text = ""
        self.heard_text = ""
        self.is_backgrounded = False
        self.current_monitor_index = 0
        self.current_position_name = "bottom_right"
        self.last_geometry = None

        self.screens = self._get_screens()
        self.ring = MayaRing(
            self.window_size_x,
            self.window_size_y,
            radius=get_env("UI_RING_RADIUS", 72, int),
            thickness=get_env("UI_RING_THICKNESS", 18, int),
        )
        self.ring.set_state("idle")

        self.root = OverlayWidget(self)
        self.root.setWindowTitle(self.window_caption)
        self.quick_input_window = QuickInputWidget(self)
        _apply_windows_overlay_style(self.root)
        _apply_windows_overlay_style(self.quick_input_window)

        self.set_scale("set", self.initial_scale)
        self.move_overlay(self.initial_position, self.initial_monitor - 1)
        self.hide_overlay()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)

    def _get_screens(self):
        screens = []
        for screen in self.app.screens():
            geometry = screen.availableGeometry()
            screens.append(
                {
                    "x": geometry.x(),
                    "y": geometry.y(),
                    "width": geometry.width(),
                    "height": geometry.height(),
                }
            )

        if screens:
            screens.sort(key=lambda item: (item["x"], item["y"]))
            return screens

        primary = self.app.primaryScreen().availableGeometry()
        return [
            {
                "x": primary.x(),
                "y": primary.y(),
                "width": primary.width(),
                "height": primary.height(),
            }
        ]

    def _get_screen(self, monitor_index):
        safe_index = max(0, min(monitor_index, len(self.screens) - 1))
        return self.screens[safe_index], safe_index

    def _resolve_monitor_index(self, monitor_value):
        if isinstance(monitor_value, str):
            normalized = monitor_value.strip().lower()
            if normalized in {"current", "same", "this"}:
                return self.current_monitor_index
            if normalized in {"other", "next", "another"}:
                if len(self.screens) <= 1:
                    return self.current_monitor_index
                return (self.current_monitor_index + 1) % len(self.screens)
            if normalized.isdigit():
                return max(0, int(normalized) - 1)

        if isinstance(monitor_value, int):
            return max(0, monitor_value - 1)

        return self.current_monitor_index

    def _compute_window_location(self, position_name, monitor_index):
        screen, safe_index = self._get_screen(monitor_index)
        x_min = screen["x"] + self.window_margin
        x_max = screen["x"] + screen["width"] - self.window_size_x - self.window_margin
        y_min = screen["y"] + self.window_margin
        y_max = screen["y"] + screen["height"] - self.window_size_y - self.window_margin
        x_center = screen["x"] + (screen["width"] - self.window_size_x) // 2
        y_center = screen["y"] + (screen["height"] - self.window_size_y) // 2

        positions = {
            "top_left": (x_min, y_min),
            "top": (x_center, y_min),
            "top_right": (x_max, y_min),
            "left": (x_min, y_center),
            "center": (x_center, y_center),
            "right": (x_max, y_center),
            "bottom_left": (x_min, y_max),
            "bottom": (x_center, y_max),
            "bottom_right": (x_max, y_max),
        }

        self.current_monitor_index = safe_index
        self.current_position_name = position_name
        return positions.get(position_name, positions["bottom_right"])

    def _apply_overlay_geometry(self, x, y):
        self.last_geometry = (int(x), int(y), self.window_size_x, self.window_size_y)
        if hasattr(self, "root") and self.root is not None:
            if hasattr(self.root, "resize"):
                self.root.resize(self.window_size_x, self.window_size_y)
            self.root.setGeometry(int(x), int(y), self.window_size_x, self.window_size_y)

    def position_quick_input(self):
        if not hasattr(self, "root") or self.root is None or not hasattr(self, "quick_input_window"):
            return
        screen, _safe_index = self._get_screen(self.current_monitor_index)
        x = screen["x"] + (screen["width"] - self.quick_input_width) // 2
        y = screen["y"] + screen["height"] - self.quick_input_height - self.window_margin
        self.quick_input_window.setGeometry(x, y, self.quick_input_width, self.quick_input_height)

    def handle_quick_input_keypress(self, _event=None):
        if self.keep_awake_callback:
            self.keep_awake_callback()

    def show_quick_input(self):
        if self.keep_awake_callback:
            self.keep_awake_callback()
        self.position_quick_input()
        self.quick_input_window.show()
        self.quick_input_window.raise_()
        self.quick_input_window.activateWindow()
        self.quick_input_window.entry.setFocus()

    def hide_quick_input(self):
        self.quick_input_window.hide()

    def set_voice_status(self, status):
        self.voice_status = status
        if status == "loading":
            self.ring.set_state("idle")
        elif status == "ready":
            self.ring.set_state("ready")
        elif status == "hearing":
            self.ring.set_state("hearing")
        elif status == "error":
            self.ring.set_state("error")
        else:
            self.ring.set_state("idle")

    def set_voice_partial(self, text):
        self.heard_text = text

    def clear_voice_partial(self):
        self.heard_text = ""

    def set_response_text(self, text):
        self.response_text = text
        self.ring.set_state("speaking", duration=0.6)

    def trigger_wake(self):
        self.ring.set_state("wake", duration=0.45)
        self.bring_to_front()

    def move_overlay(self, position_name, monitor_index):
        if not position_name or position_name == "current":
            position_name = self.current_position_name
        x, y = self._compute_window_location(position_name, monitor_index)
        self._apply_overlay_geometry(x, y)
        self.position_quick_input()
        self.bring_to_front()

    def set_scale(self, scale_mode, scale_value):
        if scale_mode == "increase":
            new_scale = self.scale_factor + scale_value
        elif scale_mode == "decrease":
            new_scale = self.scale_factor - scale_value
        else:
            new_scale = scale_value

        self.scale_factor = max(0.3, min(3.0, new_scale))
        self.window_size_x = max(120, int(self.base_window_size_x * self.scale_factor))
        self.window_size_y = max(120, int(self.base_window_size_y * self.scale_factor))
        self.ring.set_scale(self.scale_factor)
        self.move_overlay(self.current_position_name, self.current_monitor_index)

    def send_to_background(self):
        self.is_backgrounded = True
        self.hide_quick_input()
        self.root.hide()

    def hide_overlay(self):
        self.send_to_background()

    def bring_to_front(self):
        self.is_backgrounded = False
        self.root.show()
        self.root.raise_()
        self.position_quick_input()

    def handle_events(self):
        while not self.events.empty():
            event, value = self.events.get()

            if event == "voice_status":
                self.set_voice_status(value)
            elif event == "voice_partial":
                self.set_voice_partial(value)
            elif event == "voice_final":
                self.clear_voice_partial()
            elif event == "response_text":
                self.set_response_text(value)
            elif event == "double_clap":
                self.trigger_wake()
            elif event == "app_background":
                self.send_to_background()
            elif event == "app_sleep_ui":
                self.hide_overlay()
            elif event == "app_foreground":
                self.bring_to_front()
            elif event == "app_show_quick_input":
                self.show_quick_input()
            elif event == "app_hide_quick_input":
                self.hide_quick_input()
            elif event == "app_move":
                monitor_value = value.get("monitor", 1)
                self.move_overlay(
                    value.get("position", "bottom_right"),
                    self._resolve_monitor_index(monitor_value),
                )
            elif event == "app_scale":
                self.set_scale(
                    value.get("mode", "set"),
                    float(value.get("value", 1.0)),
                )
            elif event == "exit":
                self.app.quit()

    def update(self):
        self.handle_events()
        self.ring.update(1 / 60)
        if hasattr(self, "root") and self.root is not None:
            self.root.update()

        if self.periodic_callback:
            self.periodic_callback(1 / 60)

    def run(self):
        self.timer.start(16)
        self.app.exec()

    def get_fps(self):
        return "qt"
