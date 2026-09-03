import math
import os
import sys
import threading
import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from helpers.config import get_env, get_env_defaults, get_env_fields, get_env_values, get_resource_path
from helpers.dev_workspace import DevWorkspaceOrchestrator
from helpers.i18n import is_portuguese, localize_env_field, ui_text
from helpers.thoughtful_workspace import ThoughtfulWorkspaceOrchestrator
from helpers.version import get_version_display
from helpers.window_showcase import WindowShowcaseBackend


def _overlay_window_flags(is_linux=False, is_windows=False, interactive=False):
    flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint

    if interactive and not is_windows:
        flags |= Qt.Tool
    elif not interactive:
        flags |= Qt.Tool

    if is_linux and hasattr(Qt, "BypassWindowManagerHint"):
        flags |= Qt.BypassWindowManagerHint

    if is_linux and not interactive and hasattr(Qt, "WindowDoesNotAcceptFocus"):
        flags |= Qt.WindowDoesNotAcceptFocus

    return flags


def _apply_windows_overlay_style(widget, interactive=False):
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
        if interactive:
            ex_style |= WS_EX_APPWINDOW
            ex_style &= ~WS_EX_TOOLWINDOW
        else:
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


class ColorSettingInput(QWidget):
    def __init__(self, renderer, initial_value=""):
        super().__init__()
        self.renderer = renderer
        self._color_value = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.swatch = QFrame()
        self.swatch.setObjectName("settingsColorSwatch")
        self.swatch.setFixedSize(38, 38)

        self.input = QLineEdit()
        self.input.setObjectName("settingsInput")
        self.input.setReadOnly(True)

        self.button = QPushButton(self.renderer.tr("settings_pick_color"))
        self.button.setObjectName("settingsColorButton")
        self.button.clicked.connect(self.pick_color)

        layout.addWidget(self.swatch)
        layout.addWidget(self.input, 1)
        layout.addWidget(self.button)

        self.setToolTip("")
        self.set_color_text(initial_value)

    def retranslate_ui(self):
        self.button.setText(self.renderer.tr("settings_pick_color"))

    def setToolTip(self, text):
        super().setToolTip(text)
        self.input.setToolTip(text)
        self.swatch.setToolTip(text)
        self.button.setToolTip(text)

    def color_text(self):
        return self._color_value

    def set_color_text(self, value):
        color = QColor((value or "").strip())
        if color.isValid():
            self._color_value = color.name().lower()
        else:
            self._color_value = ""
        self.input.setText(self._color_value)
        swatch_color = self._color_value or "#0f1820"
        border_color = "#8ee0ff" if self._color_value else "rgba(124, 176, 212, 80)"
        self.swatch.setStyleSheet(
            f"background: {swatch_color}; border: 1px solid {border_color}; border-radius: 12px;"
        )

    def pick_color(self):
        initial = QColor(self._color_value or "#ffffff")
        color = QColorDialog.getColor(initial, self, self.renderer.tr("settings_pick_color"))
        if color.isValid():
            self.set_color_text(color.name())


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
        self.motion_x = 0.0
        self.motion_y = 0.0
        self.motion_speed = 0.0
        self.render_scale = 1.0
        self.render_alpha = 1.0
        self.palette = {
            "idle": QColor("#d8dee6"),
            "ready": QColor("#62ff8f"),
            "hearing": QColor("#ffd75e"),
            "speaking": QColor("#9ed0ff"),
            "error": QColor("#ff6b6b"),
            "wake": QColor("#62ff8f"),
            "fallback": QColor("#dcdcdc"),
            "core": QColor("#ffffff"),
        }

    def resize(self, width, height):
        self.width = width
        self.height = height
        self.center_x = width / 2.0
        self.center_y = height / 2.0

    def set_center(self, center_x, center_y):
        self.center_x = center_x
        self.center_y = center_y

    def set_scale(self, scale_factor):
        self.base_radius = self.default_radius * scale_factor
        self.base_thickness = max(2, self.default_thickness * scale_factor)

    def set_motion(self, dx, dy):
        self.motion_x = dx
        self.motion_y = dy
        self.motion_speed = min(1.8, math.hypot(dx, dy) / 34.0)

    def set_render_presence(self, scale, alpha):
        self.render_scale = max(0.0, scale)
        self.render_alpha = max(0.0, min(1.0, alpha))

    def set_state(self, state, duration=0.0):
        self.state = state
        self.state_timer = duration

        if state == "idle":
            self.target_energy = 1.8
            self.state_color = QColor(self.palette["idle"])
            self.core_color = QColor(self.palette["core"])
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "ready":
            self.target_energy = 4.0
            self.state_color = QColor(self.palette["ready"])
            self.core_color = QColor(self.palette["core"])
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "hearing":
            self.target_energy = 14.0
            self.state_color = QColor(self.palette["hearing"])
            self.core_color = QColor(self.palette["core"])
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "speaking":
            self.target_energy = 9.0
            self.state_color = QColor(self.palette["speaking"])
            self.core_color = QColor(self.palette["core"])
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "error":
            self.target_energy = 8.0
            self.state_color = QColor(self.palette["error"])
            self.core_color = QColor(self.palette["core"])
            self.background_fill = QColor(0, 0, 0, 0)
        elif state == "wake":
            self.target_energy = 22.0
            self.state_color = QColor(self.palette["wake"])
            self.core_color = QColor(self.palette["core"])
            self.background_fill = QColor(0, 0, 0, 0)
        else:
            self.target_energy = 3.0
            self.state_color = QColor(self.palette["fallback"])
            self.core_color = QColor(self.palette["core"])
            self.background_fill = QColor(0, 0, 0, 0)

    def set_palette(self, palette):
        if not palette:
            return
        for key, color in palette.items():
            if isinstance(color, QColor) and color.isValid():
                self.palette[key] = QColor(color)
        self.set_state(self.state, duration=max(0.0, self.state_timer))

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

    def _build_ring_path(self, radius, amplitude, offset, wobble_bias):
        path = QPainterPath()
        steps = 96
        motion_angle = math.atan2(self.motion_y, self.motion_x) if self.motion_speed > 0.001 else None

        for index in range(steps + 1):
            angle = (index / steps) * math.tau
            wave_a = math.sin((angle * 3.0) + (self.time * 2.8) + offset)
            wave_b = math.sin((angle * 5.0) - (self.time * 1.6) + (offset * 0.7))
            wave_c = math.sin((angle * 8.0) + (self.time * 4.4) - offset)
            radial_noise = (wave_a * 0.55 + wave_b * 0.3 + wave_c * 0.15) * amplitude

            motion_pull = 0.0
            if motion_angle is not None:
                alignment = math.cos(angle - motion_angle)
                motion_pull = alignment * (self.base_radius * 0.09 * self.motion_speed)

            tangent_push = math.sin((angle * 2.0) + (self.time * 2.0) + wobble_bias) * amplitude * 0.16
            local_radius = max(6.0, radius + radial_noise + motion_pull)

            x = self.center_x + math.cos(angle) * local_radius + math.cos(angle + math.pi / 2.0) * tangent_push
            y = self.center_y + math.sin(angle) * local_radius + math.sin(angle + math.pi / 2.0) * tangent_push
            point = QPointF(x, y)

            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)

        path.closeSubpath()
        return path

    def draw(self, painter):
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(self.render_alpha)

        painter.setPen(Qt.NoPen)
        painter.setBrush(self.background_fill)
        main_radius = self._wave_radius(0, 1.0)
        movement_bloom = 1.0 + (self.motion_speed * 0.7)
        presence_scale = max(0.16, self.render_scale)
        fill_path = self._build_ring_path(
            (main_radius + self.base_thickness) * presence_scale,
            (self.energy * 0.45 + self.base_thickness * 0.12) * movement_bloom,
            0.0,
            0.15,
        )
        painter.drawPath(fill_path)

        outer_pen = QPen(self.state_color, 5.5)
        outer_pen.setCapStyle(Qt.RoundCap)
        outer_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(outer_pen)
        painter.drawPath(
            self._build_ring_path(
                self._wave_radius(18, 1.16) * presence_scale,
                (self.energy * 0.78 + 3.0) * movement_bloom,
                1.1,
                0.45,
            )
        )

        main_pen = QPen(self.core_color, self.base_thickness)
        main_pen.setCapStyle(Qt.RoundCap)
        main_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(main_pen)
        painter.drawPath(
            self._build_ring_path(
                main_radius * presence_scale,
                (self.energy * 0.62 + self.base_thickness * 0.15) * movement_bloom,
                0.35,
                0.75,
            )
        )

        inner_pen = QPen(self.state_color, 4)
        inner_pen.setCapStyle(Qt.RoundCap)
        inner_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(inner_pen)
        painter.drawPath(
            self._build_ring_path(
                self._wave_radius(-11, 0.78) * presence_scale,
                (self.energy * 0.48 + 2.2) * movement_bloom,
                -0.75,
                1.2,
            )
        )
        painter.setOpacity(1.0)


class OverlayWidget(QWidget):
    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        flags = _overlay_window_flags(
            is_linux=self.renderer.is_linux,
            is_windows=self.renderer.is_windows,
            interactive=False,
        )
        if self.renderer.is_linux and hasattr(Qt, "WindowTransparentForInput"):
            flags |= Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.resize(renderer.window_size_x, renderer.window_size_y)
        self._update_mask()

    def _update_mask(self):
        if self.renderer.window_positioning_limited:
            self.clearMask()
            return
        self.setMask(QRegion(self.rect(), QRegion.Ellipse))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_mask()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self.renderer.prepare_ring_for_paint(self.width(), self.height())
        self.renderer.ring.draw(painter)


class WindowShowcaseWidget(QWidget):
    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        flags = _overlay_window_flags(
            is_linux=self.renderer.is_linux,
            is_windows=self.renderer.is_windows,
            interactive=True,
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.hide()

    def sync_geometry(self):
        screen, _safe_index = self.renderer._get_screen(self.renderer.current_monitor_index)
        self.setGeometry(screen["x"], screen["y"], screen["width"], screen["height"])

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_geometry()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Q):
            self.renderer.hide_window_showcase(restore_windows=True)
            event.accept()
            return
        if event.key() in (Qt.Key_Left, Qt.Key_A):
            self.renderer.rotate_window_showcase(-1)
            event.accept()
            return
        if event.key() in (Qt.Key_Right, Qt.Key_D):
            self.renderer.rotate_window_showcase(1)
            event.accept()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.renderer.activate_selected_showcase_window()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        angle_delta = event.angleDelta().y()
        if angle_delta:
            self.renderer.rotate_window_showcase(-1 if angle_delta > 0 else 1)
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            midpoint = self.width() / 2.0
            self.renderer.rotate_window_showcase(-1 if event.position().x() < midpoint else 1)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self.renderer.hide_window_showcase(restore_windows=True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.renderer.activate_selected_showcase_window()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self.renderer.paint_window_showcase(painter, self.rect())


class QuickInputWidget(QWidget):
    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        flags = _overlay_window_flags(
            is_linux=self.renderer.is_linux,
            is_windows=self.renderer.is_windows,
            interactive=True,
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.resize(renderer.quick_input_width, renderer.quick_input_height)

        container = QFrame(self)
        container.setObjectName("quickInputCard")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(11)

        header = QHBoxLayout()
        self.brand_label = QLabel("MAYA")
        self.brand_label.setObjectName("quickInputBrand")
        self.status_label = QLabel(self.renderer.tr("quick_input_status_ready"))
        self.status_label.setObjectName("quickInputStatus")
        header.addWidget(self.brand_label)
        header.addStretch(1)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        self.response_label = QLabel(self.renderer.response_text or self.renderer.tr("quick_input_welcome"))
        self.response_label.setObjectName("quickInputResponse")
        self.response_label.setWordWrap(True)
        self.response_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.response_label.setMaximumHeight(54)
        layout.addWidget(self.response_label)

        input_shell = QFrame()
        input_shell.setObjectName("quickInputField")
        input_layout = QHBoxLayout(input_shell)
        input_layout.setContentsMargins(13, 7, 8, 7)

        self.entry = QLineEdit()
        self.entry.setObjectName("quickInputEntry")
        self.entry.setPlaceholderText(self.renderer.tr("quick_input_placeholder"))
        self.entry.returnPressed.connect(self.submit_text)
        self.entry.textEdited.connect(lambda _text: self.renderer.handle_quick_input_keypress())
        self.entry.installEventFilter(self)
        input_layout.addWidget(self.entry, 1)
        self.send_button = QPushButton("➜")
        self.send_button.setObjectName("quickInputSend")
        self.send_button.setToolTip(self.renderer.tr("quick_input_send"))
        self.send_button.clicked.connect(self.submit_text)
        input_layout.addWidget(self.send_button)
        layout.addWidget(input_shell)

        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(7)
        self.shortcut_buttons = []
        for label_key, command in (("quick_input_today", "!today"), ("quick_input_status", "!status"), ("quick_input_week", "!week")):
            button = QPushButton(self.renderer.tr(label_key))
            button.setObjectName("quickInputChip")
            button.clicked.connect(lambda _checked=False, value=command: self.submit_command(value))
            shortcuts.addWidget(button)
            self.shortcut_buttons.append((button, label_key))
        shortcuts.addStretch(1)
        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("quickInputSettings")
        self.settings_button.setToolTip(self.renderer.tr("quick_input_settings"))
        self.settings_button.clicked.connect(lambda _checked=False: self.renderer.show_settings())
        shortcuts.addWidget(self.settings_button)
        layout.addLayout(shortcuts)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(container)

        self.setStyleSheet(
            """
            QFrame#quickInputCard {
                background: rgba(10, 12, 24, 246);
                border: 1px solid rgba(145, 126, 255, 120);
                border-radius: 26px;
            }
            QLabel#quickInputBrand { color: rgb(236, 233, 255); font-size: 13px; font-weight: 800; letter-spacing: 3px; }
            QLabel#quickInputStatus { background: rgba(94, 234, 212, 30); border: 1px solid rgba(94, 234, 212, 80); border-radius: 9px; color: rgb(153, 246, 228); font-size: 10px; font-weight: 700; padding: 3px 9px; }
            QLabel#quickInputResponse { color: rgba(230, 235, 255, 205); font-size: 12px; padding: 0 2px; }
            QFrame#quickInputField { background: rgba(255, 255, 255, 12); border: 1px solid rgba(166, 180, 255, 55); border-radius: 15px; }
            QLineEdit#quickInputEntry {
                background: transparent;
                border: none;
                color: rgb(239, 247, 255);
                font-size: 15px;
                selection-background-color: rgba(139, 116, 255, 150);
            }
            QLineEdit::placeholder {
                color: rgba(220, 235, 255, 120);
            }
            QPushButton#quickInputSend { background: rgb(124, 92, 255); border: none; border-radius: 11px; color: white; font-size: 17px; font-weight: 700; min-width: 34px; min-height: 30px; }
            QPushButton#quickInputSend:hover { background: rgb(145, 119, 255); }
            QPushButton#quickInputChip, QPushButton#quickInputSettings { background: rgba(255, 255, 255, 9); border: 1px solid rgba(190, 199, 255, 38); border-radius: 10px; color: rgba(226, 230, 255, 190); font-size: 11px; padding: 5px 10px; }
            QPushButton#quickInputChip:hover, QPushButton#quickInputSettings:hover { background: rgba(124, 92, 255, 45); border-color: rgba(155, 134, 255, 100); color: white; }
            """
        )
        self.hide()

    def retranslate_ui(self):
        self.entry.setPlaceholderText(self.renderer.tr("quick_input_placeholder"))
        self.send_button.setToolTip(self.renderer.tr("quick_input_send"))
        self.settings_button.setToolTip(self.renderer.tr("quick_input_settings"))
        for button, label_key in self.shortcut_buttons:
            button.setText(self.renderer.tr(label_key))

    def submit_command(self, command):
        self.entry.setText(command)
        self.submit_text(keep_open=True)

    def set_response(self, text):
        if text:
            compact = " ".join(str(text).split())
            self.response_label.setText(compact[:220] + ("…" if len(compact) > 220 else ""))

    def set_status(self, status):
        keys = {"hearing": "quick_input_status_listening", "speaking": "quick_input_status_speaking", "error": "quick_input_status_error"}
        self.status_label.setText(self.renderer.tr(keys.get(status, "quick_input_status_ready")))

    def eventFilter(self, _obj, event):
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key_Escape:
            self.renderer.hide_quick_input()
            return True
        return False

    def submit_text(self, keep_open=False):
        submitted_text = self.entry.text().strip()
        if submitted_text:
            if submitted_text == "exit":
                self.renderer.app.quit()
                return
            self.renderer.submit_input_callback(submitted_text)
        self.entry.clear()
        if not keep_open:
            self.renderer.hide_quick_input()


class DevEditorWidget(QWidget):
    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        self.current_file_path = None

        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.resize(1080, 760)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.path_label = QLabel(self.renderer.tr("dev_editor_title"))
        self.path_label.setStyleSheet("color: #d6dfeb; font-size: 13px; font-weight: 600;")

        self.new_button = QPushButton(self.renderer.tr("dev_editor_new"))
        self.open_button = QPushButton(self.renderer.tr("dev_editor_open"))
        self.save_button = QPushButton(self.renderer.tr("dev_editor_save"))
        self.save_as_button = QPushButton(self.renderer.tr("dev_editor_save_as"))

        for button in (self.new_button, self.open_button, self.save_button, self.save_as_button):
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(34)
            button.setStyleSheet(
                "QPushButton {"
                "background: #142033;"
                "color: #ecf2f8;"
                "border: 1px solid #2a4263;"
                "border-radius: 10px;"
                "padding: 6px 12px;"
                "font-size: 12px;"
                "font-weight: 600;"
                "}"
                "QPushButton:hover { background: #1b2c46; }"
            )

        toolbar.addWidget(self.path_label, 1)
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.save_button)
        toolbar.addWidget(self.save_as_button)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(self.renderer.tr("dev_editor_placeholder"))
        self.editor.setTabStopDistance(32)
        editor_font = QFont("JetBrains Mono")
        editor_font.setStyleHint(QFont.Monospace)
        editor_font.setPointSize(12)
        self.editor.setFont(editor_font)
        self.editor.setStyleSheet(
            "QPlainTextEdit {"
            "background: #08111d;"
            "color: #e7eef7;"
            "border: 1px solid #1d324b;"
            "border-radius: 16px;"
            "padding: 14px;"
            "selection-background-color: #234c82;"
            "}"
        )

        self.status_label = QLabel(self.renderer.tr("dev_editor_ready"))
        self.status_label.setStyleSheet("color: #97abc4; font-size: 12px;")

        root_layout.addLayout(toolbar)
        root_layout.addWidget(self.editor, 1)
        root_layout.addWidget(self.status_label)

        self.setStyleSheet("background: #060c14;")

        self.new_button.clicked.connect(self.new_file)
        self.open_button.clicked.connect(self.open_file)
        self.save_button.clicked.connect(self.save_file)
        self.save_as_button.clicked.connect(self.save_file_as)

        self._load_default_template()

    def retranslate_ui(self):
        self.new_button.setText(self.renderer.tr("dev_editor_new"))
        self.open_button.setText(self.renderer.tr("dev_editor_open"))
        self.save_button.setText(self.renderer.tr("dev_editor_save"))
        self.save_as_button.setText(self.renderer.tr("dev_editor_save_as"))
        self.editor.setPlaceholderText(self.renderer.tr("dev_editor_placeholder"))
        if not self.current_file_path:
            self.path_label.setText(self.renderer.tr("dev_editor_title"))
        self._update_title()

    def _load_default_template(self):
        self.editor.setPlainText(
            "def main():\n"
            f"    print('{self.renderer.tr('dev_editor_template_message')}')\n"
            "\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        self.current_file_path = None
        self._update_title()
        self.status_label.setText(self.renderer.tr("dev_editor_default_status"))
        self.editor.document().setModified(False)

    def _update_title(self):
        label = self.current_file_path or self.renderer.tr("dev_editor_title")
        self.setWindowTitle(self.renderer.tr("dev_editor_window_title", caption=self.renderer.window_caption))
        self.path_label.setText(label)

    def new_file(self):
        self._load_default_template()

    def open_file(self):
        start_dir = os.getcwd()
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self.renderer.tr("dev_editor_open_dialog_title"),
            start_dir,
            "Code files (*.py *.js *.ts *.tsx *.jsx *.json *.md *.html *.css *.sh *.txt);;All files (*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                self.editor.setPlainText(file.read())
            self.current_file_path = file_path
            self._update_title()
            self.status_label.setText(self.renderer.tr("dev_editor_opened", name=os.path.basename(file_path)))
            self.editor.document().setModified(False)
        except Exception as error:
            self.status_label.setText(self.renderer.tr("dev_editor_open_failed", error=error))

    def save_file(self):
        if not self.current_file_path:
            return self.save_file_as()
        try:
            with open(self.current_file_path, "w", encoding="utf-8") as file:
                file.write(self.editor.toPlainText())
            self._update_title()
            self.status_label.setText(self.renderer.tr("dev_editor_saved", name=os.path.basename(self.current_file_path)))
            self.editor.document().setModified(False)
            return True
        except Exception as error:
            self.status_label.setText(self.renderer.tr("dev_editor_save_failed", error=error))
            return False

    def save_file_as(self):
        start_dir = os.getcwd()
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            self.renderer.tr("dev_editor_save_dialog_title"),
            start_dir,
            "Code files (*.py *.js *.ts *.tsx *.jsx *.json *.md *.html *.css *.sh *.txt);;All files (*)",
        )
        if not file_path:
            return False
        self.current_file_path = file_path
        return self.save_file()


class SettingsWindow(QWidget):
    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        self.inputs = {}

        self.setObjectName("settingsWindow")
        self.setWindowTitle(self.renderer.tr("settings_window_title"))
        self.resize(860, 760)
        self.setMinimumSize(740, 640)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("settingsHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 17, 22, 17)
        header_layout.setSpacing(4)
        self.title_label = QLabel(self.renderer.tr("settings_title"))
        self.title_label.setObjectName("settingsTitle")
        self.subtitle_label = QLabel(self.renderer.tr("settings_subtitle"))
        self.subtitle_label.setObjectName("settingsSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.version_label = QLabel(self.renderer.tr("settings_version", version=self.renderer.app_version_display))
        self.version_label.setObjectName("settingsVersion")
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.subtitle_label)
        header_layout.addWidget(self.version_label)
        root_layout.addWidget(header)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(self.renderer.tr("settings_filter_placeholder"))
        self.filter_input.setObjectName("settingsInput")
        self.filter_input.textChanged.connect(self.apply_filter)
        self.category_filter = QComboBox()
        self.category_filter.setObjectName("settingsCategoryFilter")
        self.category_filter.setMinimumWidth(190)
        self.category_filter.currentIndexChanged.connect(lambda _index: self.apply_filter(self.filter_input.text()))
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        search_row.addWidget(self.filter_input, 1)
        search_row.addWidget(self.category_filter)
        root_layout.addLayout(search_row)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        scroll_content.setObjectName("settingsScrollContent")
        self.sections_layout = QVBoxLayout(scroll_content)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(14)
        self.sections = []
        self.field_rows = []

        current_category = None
        current_form = None
        current_section = None
        for field in get_env_fields():
            localized = localize_env_field(field, self.renderer.language)
            if localized["category"] != current_category:
                section = QFrame()
                section.setObjectName("settingsSection")
                section_layout = QVBoxLayout(section)
                section_layout.setContentsMargins(18, 14, 18, 16)
                section_layout.setSpacing(8)

                section_title = QLabel(localized["category"])
                section_title.setObjectName("settingsSectionTitle")
                section_layout.addWidget(section_title)

                current_form = QFormLayout()
                current_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
                current_form.setFormAlignment(Qt.AlignTop)
                current_form.setHorizontalSpacing(22)
                current_form.setVerticalSpacing(10)
                section_layout.addLayout(current_form)
                self.sections_layout.addWidget(section)
                self.sections.append(
                    {
                        "widget": section,
                        "category": localized["category"],
                        "title": section_title,
                    }
                )
                current_category = localized["category"]
                current_section = section

            label = QLabel(localized["label"])
            label.setObjectName("settingsLabel")
            label.setToolTip(localized["help_text"])

            if field.key.startswith("UI_COLOR_"):
                control = ColorSettingInput(self.renderer, field.default)
            elif field.options:
                control = QComboBox()
                control.addItems(list(field.options))
                control.setEditable(False)
            else:
                control = QLineEdit()
                control.setPlaceholderText(field.default)

            control.setObjectName("settingsInput")
            control.setToolTip(localized["help_text"])
            self.inputs[field.key] = control

            field_layout = QVBoxLayout()
            field_layout.setSpacing(4)
            field_layout.addWidget(control)
            if localized["help_text"]:
                help_label = QLabel(localized["help_text"])
                help_label.setObjectName("settingsHelp")
                help_label.setWordWrap(True)
                field_layout.addWidget(help_label)
            else:
                help_label = None

            current_form.addRow(label, field_layout)
            self.field_rows.append(
                {
                    "field": field,
                    "label": label,
                    "control": control,
                    "layout": field_layout,
                    "help_label": help_label,
                    "section": current_section,
                    "section_entry": self.sections[-1],
                }
            )

        self.sections_layout.addStretch(1)
        self.category_filter.clear()
        self.category_filter.addItem("Todas as categorias" if is_portuguese(self.renderer.language) else "All categories", "")
        for section in self.sections:
            self.category_filter.addItem(section["category"], section["category"])
        scroll_area.setWidget(scroll_content)
        root_layout.addWidget(scroll_area, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions_frame = QFrame()
        actions_frame.setObjectName("settingsActions")
        actions_frame.setLayout(actions)
        self.status_label = QLabel("")
        self.status_label.setObjectName("settingsStatus")
        actions.addWidget(self.status_label, 1)

        self.refresh_button = QPushButton(self.renderer.tr("settings_reload"))
        self.refresh_button.clicked.connect(self.load_values)
        self.defaults_button = QPushButton(self.renderer.tr("settings_defaults"))
        self.defaults_button.clicked.connect(self.load_defaults)
        self.apply_button = QPushButton(self.renderer.tr("settings_apply"))
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.clicked.connect(self.apply_changes)
        self.close_button = QPushButton(self.renderer.tr("settings_close"))
        self.close_button.clicked.connect(self.hide)

        for button in (self.refresh_button, self.defaults_button, self.apply_button, self.close_button):
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(40)

        actions.addWidget(self.refresh_button)
        actions.addWidget(self.defaults_button)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.close_button)
        root_layout.addWidget(actions_frame)

        self.setStyleSheet(
            """
            QWidget#settingsWindow {
                background: #0b0d14;
                color: #edf6ff;
                font-size: 14px;
            }
            QWidget#settingsScrollContent, QScrollArea, QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            QFrame#settingsHeader {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #19152b,
                    stop: 0.55 #14182a,
                    stop: 1 #10242a
                );
                border: 1px solid rgba(148, 123, 255, 110);
                border-radius: 18px;
            }
            QFrame#settingsSection {
                background: #121722;
                border: 1px solid #252d3d;
                border-radius: 14px;
            }
            QLabel#settingsTitle {
                font-size: 26px;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#settingsSubtitle {
                color: rgba(225, 239, 250, 190);
                font-size: 13px;
            }
            QLabel#settingsVersion {
                color: #8fe3bd;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            QLabel#settingsSectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #a996ff;
                padding: 0 0 5px 2px;
            }
            QLabel#settingsLabel {
                font-weight: 600;
                padding: 7px 0 0 2px;
                color: #e6e9f2;
            }
            QLabel#settingsHelp {
                color: #8791a5;
                font-size: 12px;
            }
            QLabel#settingsStatus {
                color: #8de0b1;
                padding-left: 4px;
            }
            QFrame#settingsActions {
                background: #111620;
                border: 1px solid #252d3d;
                border-radius: 14px;
                padding: 6px;
            }
            QLineEdit, QComboBox {
                min-height: 38px;
                border-radius: 10px;
                border: 1px solid #313b50;
                background: #0d111a;
                padding: 0 12px;
                selection-background-color: rgba(74, 178, 235, 145);
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #9278ff;
                background: #121624;
            }
            QComboBox::drop-down {
                width: 34px;
                border: none;
                border-left: 1px solid #313b50;
            }
            QComboBox QAbstractItemView {
                background: #151a27;
                color: #edf6ff;
                border: 1px solid #9278ff;
                selection-background-color: #5845a5;
            }
            QPushButton#settingsColorButton {
                min-width: 88px;
            }
            QPushButton {
                min-height: 40px;
                border-radius: 10px;
                border: 1px solid #354057;
                background: #1a2130;
                padding: 0 16px;
                color: #e9f5fc;
            }
            QPushButton:hover {
                background: #252d40;
                border-color: #9278ff;
            }
            QPushButton:pressed {
                background: #121724;
            }
            QPushButton#primaryButton {
                background: #8f72ff;
                color: #ffffff;
                border-color: #9c84ff;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background: #a58fff;
                border-color: #b4a2ff;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 4px 0 4px 4px;
            }
            QScrollBar::handle:vertical {
                background: #4c5670;
                border-radius: 5px;
                min-height: 32px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9278ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0;
            }
            """
        )

        self.hide()

    def retranslate_ui(self):
        self.setWindowTitle(self.renderer.tr("settings_window_title"))
        self.title_label.setText(self.renderer.tr("settings_title"))
        self.subtitle_label.setText(self.renderer.tr("settings_subtitle"))
        self.version_label.setText(self.renderer.tr("settings_version", version=self.renderer.app_version_display))
        self.filter_input.setPlaceholderText(self.renderer.tr("settings_filter_placeholder"))
        self.refresh_button.setText(self.renderer.tr("settings_reload"))
        self.defaults_button.setText(self.renderer.tr("settings_defaults"))
        self.apply_button.setText(self.renderer.tr("settings_apply"))
        self.close_button.setText(self.renderer.tr("settings_close"))
        for section in self.sections:
            section["title"].setText(section["category"])
        for row in self.field_rows:
            localized = localize_env_field(row["field"], self.renderer.language)
            row["label"].setText(localized["label"])
            row["label"].setToolTip(localized["help_text"])
            row["control"].setToolTip(localized["help_text"])
            if isinstance(row["control"], ColorSettingInput):
                row["control"].retranslate_ui()
            if row["help_label"] is not None:
                row["help_label"].setText(localized["help_text"])
            row["section_entry"]["category"] = localized["category"]
            row["section_entry"]["title"].setText(localized["category"])

    def _set_control_value(self, control, value):
        text = "" if value is None else str(value)
        if isinstance(control, QComboBox):
            index = control.findText(text, Qt.MatchFixedString)
            if index >= 0:
                control.setCurrentIndex(index)
            elif control.count() > 0:
                control.setCurrentIndex(0)
        elif isinstance(control, ColorSettingInput):
            control.set_color_text(text)
        else:
            control.setText(text)

    def _get_control_value(self, control):
        if isinstance(control, QComboBox):
            return control.currentText().strip()
        if isinstance(control, ColorSettingInput):
            return control.color_text().strip()
        return control.text().strip()

    def load_values(self):
        values = self.renderer.get_settings_values()
        for key, control in self.inputs.items():
            self._set_control_value(control, values.get(key, ""))
        self.status_label.setText("")
        self.apply_filter(self.filter_input.text())

    def load_defaults(self):
        values = get_env_defaults()
        for key, control in self.inputs.items():
            self._set_control_value(control, values.get(key, ""))
        self.status_label.setText(self.renderer.tr("settings_loaded_defaults"))
        self.apply_filter(self.filter_input.text())

    def apply_filter(self, text):
        normalized = (text or "").strip().lower()
        selected_category = self.category_filter.currentData() or ""
        visible_sections = set()

        for row in self.field_rows:
            field = row["field"]
            localized = localize_env_field(field, self.renderer.language)
            haystack = " ".join(
                [
                    field.key,
                    localized["category"],
                    localized["label"],
                    localized["help_text"],
                ]
            ).lower()
            category_matches = not selected_category or localized["category"] == selected_category
            visible = category_matches and (not normalized or normalized in haystack)
            row["label"].setVisible(visible)
            row["control"].setVisible(visible)
            row["layout"].itemAt(0).widget().setVisible(visible)
            if row["help_label"] is not None:
                row["help_label"].setVisible(visible)
            if visible:
                visible_sections.add(row["section"])

        for section in self.sections:
            section["widget"].setVisible(
                section["widget"] in visible_sections
                or (not normalized and not selected_category)
            )

    def apply_changes(self):
        values = {
            key: self._get_control_value(control)
            for key, control in self.inputs.items()
        }
        success, message = self.renderer.apply_settings_callback(values)
        self.status_label.setText(message)
        if success:
            self.load_values()


class Renderer:
    def __init__(
        self,
        events,
        submit_input_callback,
        periodic_callback=None,
        keep_awake_callback=None,
        settings_apply_callback=None,
        settings_values_callback=None,
    ):
        self.events = events
        self.submit_input_callback = submit_input_callback
        self.periodic_callback = periodic_callback
        self.keep_awake_callback = keep_awake_callback
        self.language = get_env("LANGUAGE", "en")
        self.apply_settings_callback = settings_apply_callback or (lambda _values: (False, self.tr("settings_apply_callback_missing")))
        self.settings_values_callback = settings_values_callback or get_env_values

        self.window_size_x = get_env("WINDOW_WIDTH", 260, int)
        self.window_size_y = get_env("WINDOW_HEIGHT", 260, int)
        self.base_window_size_x = self.window_size_x
        self.base_window_size_y = self.window_size_y
        self.window_caption = "maya"
        self.app_version_display = get_version_display()
        self.overlay_window_title = self.tr("overlay_window_title", caption=self.window_caption)
        self.showcase_window_title = self.tr("showcase_window_title", caption=self.window_caption)
        self.quick_input_window_title = self.tr("quick_input_window_title", caption=self.window_caption)
        self.settings_window_title = self.tr("settings_window_caption", caption=self.window_caption)
        self.window_margin = get_env("WINDOW_MARGIN", 32, int)
        self.quick_input_width = get_env("QUICK_INPUT_WIDTH", 420, int)
        self.quick_input_height = max(210, get_env("QUICK_INPUT_HEIGHT", 210, int))
        self.scale_factor = 1.0
        self.initial_position = get_env("INITIAL_POSITION", "top_right")
        self.initial_monitor = max(1, get_env("INITIAL_MONITOR", 2, int))
        self.initial_scale = get_env("INITIAL_SCALE", 0.5, float)
        self.is_linux = sys.platform.startswith("linux")
        self.is_windows = sys.platform.startswith("win")
        self.window_positioning_limited = self.is_linux and os.getenv("XDG_SESSION_TYPE", "").strip().lower() == "wayland"

        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.voice_status = "idle"
        self.response_text = ""
        self.heard_text = ""
        self.is_backgrounded = False
        self.current_monitor_index = 0
        self.current_position_name = "bottom_right"
        self.last_geometry = None
        self.ring_center = None
        self.current_draw_x = 0.0
        self.current_draw_y = 0.0
        self.target_draw_x = 0.0
        self.target_draw_y = 0.0
        self.current_draw_monitor_index = 0
        self.target_monitor_index = 0
        self.monitor_transition_phase = None
        self.monitor_transition_progress = 0.0
        self.monitor_transition_duration = 0.22
        self.monitor_transition_source_monitor = None
        self.monitor_transition_target_position = None
        self.monitor_transition_target_monitor = None
        self.showcase_entries = []
        self.showcase_message = ""
        self.showcase_selected_index = 0
        self.showcase_current_rotation = 0.0
        self.showcase_target_rotation = 0.0
        self.showcase_preview_cache = {}
        self.showcase_preview_refresh_interval = 1.15
        self.showcase_last_preview_refresh_at = 0.0
        self.external_window_drag = None
        self.external_window_action = None
        self.showcase_scale_pulse = 0.0
        self.showcase_minimized_window_ids = []
        self.showcase_restore_on_hide = False
        self.dev_mode_animation_active = False
        self.dev_mode_animation_started_at = 0.0
        self.dev_mode_animation_duration = 2.8
        self.dev_mode_last_spin_at = 0.0
        self.dev_mode_showcase_auto_opened = False
        self.dev_mode_worker = None

        self.screens = self._get_screens()
        self.ring = MayaRing(
            self.window_size_x,
            self.window_size_y,
            radius=get_env("UI_RING_RADIUS", 72, int),
            thickness=get_env("UI_RING_THICKNESS", 18, int),
        )
        self._apply_ring_palette_from_settings()
        self.ring.set_state("idle")

        self.root = OverlayWidget(self)
        self.root.setWindowTitle(self.overlay_window_title)
        self.window_catalog = WindowShowcaseBackend(own_pid=os.getpid(), own_caption=self.window_caption)
        self.window_showcase_window = WindowShowcaseWidget(self)
        self.quick_input_window = QuickInputWidget(self)
        self.dev_editor_window = DevEditorWidget(self)
        self.settings_window = SettingsWindow(self)
        self.window_showcase_window.setWindowTitle(self.showcase_window_title)
        self.quick_input_window.setWindowTitle(self.quick_input_window_title)
        self.settings_window.setWindowTitle(self.settings_window_title)
        self._create_tray_icon()
        _apply_windows_overlay_style(self.root, interactive=False)
        _apply_windows_overlay_style(self.quick_input_window, interactive=True)
        _apply_windows_overlay_style(self.window_showcase_window, interactive=True)

        self.set_scale("set", self.initial_scale)
        self.move_overlay(self.initial_position, self.initial_monitor - 1)
        self.hide_overlay()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)

    def _create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(QIcon(str(get_resource_path("icon.ico"))), self.app)
        self.tray_icon.setToolTip("Maya — clique para chamar")

        tray_menu = QMenu()
        call_action = QAction("Chamar Maya", tray_menu)
        settings_action = QAction("Configurações", tray_menu)
        quit_action = QAction("Sair", tray_menu)
        call_action.triggered.connect(self._call_from_tray)
        settings_action.triggered.connect(self.show_settings)
        quit_action.triggered.connect(self.app.quit)
        tray_menu.addAction(call_action)
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _call_from_tray(self):
        self.bring_to_front()
        self.show_quick_input()
        if self.keep_awake_callback:
            self.keep_awake_callback()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._call_from_tray()

    def tr(self, key, **kwargs):
        english = {
            "quick_input_placeholder": "Talk to Maya...",
            "quick_input_welcome": "Ready when you are. Ask anything or use a shortcut.",
            "quick_input_send": "Send",
            "quick_input_today": "Today",
            "quick_input_status": "Status",
            "quick_input_week": "Week",
            "quick_input_settings": "Settings",
            "quick_input_status_ready": "READY",
            "quick_input_status_listening": "LISTENING",
            "quick_input_status_speaking": "SPEAKING",
            "quick_input_status_error": "OFFLINE",
            "dev_editor_title": "maya dev editor",
            "dev_editor_window_title": "{caption} dev editor",
            "dev_editor_new": "New",
            "dev_editor_open": "Open",
            "dev_editor_save": "Save",
            "dev_editor_save_as": "Save As",
            "dev_editor_placeholder": "// maya dev editor\n",
            "dev_editor_ready": "Ready.",
            "dev_editor_default_status": "New scratch file.",
            "dev_editor_open_dialog_title": "Open file in Maya editor",
            "dev_editor_save_dialog_title": "Save file from Maya editor",
            "dev_editor_opened": "Opened {name}.",
            "dev_editor_open_failed": "Could not open file: {error}",
            "dev_editor_saved": "Saved {name}.",
            "dev_editor_save_failed": "Could not save file: {error}",
            "dev_editor_template_message": "maya dev mode is ready",
            "settings_window_title": "Maya User Settings",
            "settings_title": "Maya User Settings",
            "settings_subtitle": "Edit `.env` values here and apply changes immediately.",
            "settings_filter_placeholder": "Filter settings by name, category, or help text",
            "settings_reload": "Reload",
            "settings_defaults": "Reset Defaults",
            "settings_apply": "Apply",
            "settings_close": "Close",
            "settings_pick_color": "Pick Color",
            "settings_version": "Version: {version}",
            "settings_loaded_defaults": "Loaded default values into the form.",
            "settings_apply_callback_missing": "Settings apply callback not configured.",
            "showcase_title": "window disco",
            "showcase_empty": "No open windows available for the showcase.",
            "showcase_focus_failed": "I could not focus that window.",
            "showcase_active": "ACTIVE",
            "showcase_status": "left/right or mouse wheel to rotate. enter to focus. esc to close.",
            "overlay_window_title": "{caption} overlay",
            "showcase_window_title": "{caption} showcase",
            "quick_input_window_title": "{caption} quick input",
            "settings_window_caption": "{caption} settings",
        }
        if is_portuguese(self.language):
            return ui_text(key, self.language, **kwargs)
        template = english.get(key, key)
        return template.format(**kwargs) if kwargs else template

    @staticmethod
    def _color_from_env(key, fallback):
        value = str(get_env(key, fallback) or "").strip()
        color = QColor(value)
        if color.isValid():
            return color
        return QColor(fallback)

    def _apply_ring_palette_from_settings(self):
        ready_color = self._color_from_env("UI_COLOR_READY", "#62ff8f")
        palette = {
            "idle": self._color_from_env("UI_COLOR_IDLE", "#d8dee6"),
            "ready": ready_color,
            "hearing": self._color_from_env("UI_COLOR_HEARING", "#ffd75e"),
            "speaking": self._color_from_env("UI_COLOR_SPEAKING", "#9ed0ff"),
            "error": self._color_from_env("UI_COLOR_ERROR", "#ff6b6b"),
            "wake": ready_color,
            "fallback": self._color_from_env("UI_COLOR_IDLE", "#dcdcdc"),
            "core": self._color_from_env("UI_COLOR_CORE", "#ffffff"),
        }
        self.ring.set_palette(palette)

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
                    "handle": screen,
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
                "handle": self.app.primaryScreen(),
            }
        ]

    def refresh_screens(self):
        self.screens = self._get_screens()
        if self.current_monitor_index >= len(self.screens):
            self.current_monitor_index = max(0, len(self.screens) - 1)
        return self.screens

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

    def _set_wayland_screen(self, monitor_index):
        screen, safe_index = self._get_screen(monitor_index)
        window_handle = self.root.windowHandle()
        if window_handle and screen.get("handle") is not None:
            try:
                window_handle.setScreen(screen["handle"])
            except Exception:
                pass
        return screen, safe_index

    def _set_ring_center_from_global_position(self, x, y, monitor_index):
        screen, _safe_index = self._get_screen(monitor_index)
        center_x = (x - screen["x"]) + (self.window_size_x / 2.0)
        center_y = (y - screen["y"]) + (self.window_size_y / 2.0)
        self.ring_center = (center_x, center_y)

    def _apply_overlay_geometry(self, x, y):
        self.last_geometry = (int(x), int(y), self.window_size_x, self.window_size_y)
        if hasattr(self, "root") and self.root is not None:
            if hasattr(self.root, "resize"):
                self.root.resize(self.window_size_x, self.window_size_y)
            self.root.move(int(x), int(y))
            self.root.setGeometry(int(x), int(y), self.window_size_x, self.window_size_y)

    def _apply_wayland_overlay_geometry(self, monitor_index, x, y):
        screen, safe_index = self._set_wayland_screen(monitor_index)
        self.current_monitor_index = safe_index
        self.last_geometry = (int(x), int(y), self.window_size_x, self.window_size_y)
        self.root.setGeometry(screen["x"], screen["y"], screen["width"], screen["height"])
        self.root.resize(screen["width"], screen["height"])
        self._set_ring_center_from_global_position(x, y, safe_index)

    def _apply_current_position(self):
        if self.window_positioning_limited:
            self._apply_wayland_overlay_geometry(self.current_draw_monitor_index, self.current_draw_x, self.current_draw_y)
        else:
            self._apply_overlay_geometry(self.current_draw_x, self.current_draw_y)

    def _snap_to_position(self, x, y, monitor_index=None):
        safe_monitor = self.current_monitor_index if monitor_index is None else monitor_index
        self.current_monitor_index = safe_monitor
        self.current_draw_monitor_index = safe_monitor
        self.target_monitor_index = safe_monitor
        self.current_draw_x = float(x)
        self.current_draw_y = float(y)
        self.target_draw_x = float(x)
        self.target_draw_y = float(y)
        self.ring.set_motion(0.0, 0.0)
        self._apply_current_position()

    def _force_monitor_jump(self, x, y, monitor_index):
        self.current_monitor_index = monitor_index
        self.current_draw_monitor_index = monitor_index
        self.target_monitor_index = monitor_index
        self.current_draw_x = float(x)
        self.current_draw_y = float(y)
        self.target_draw_x = float(x)
        self.target_draw_y = float(y)
        self.ring.set_motion(0.0, 0.0)

        if self.window_positioning_limited:
            self.root.hide()
            self._apply_wayland_overlay_geometry(monitor_index, x, y)
            self.root.show()
        else:
            self._apply_overlay_geometry(x, y)
        # The overlay has now landed on the target monitor. Keep the
        # interactive input window attached to the same effective monitor.
        self.position_quick_input()
        self.position_dev_editor()

    def _set_target_position(self, x, y, monitor_index):
        monitor_changed = monitor_index != self.current_draw_monitor_index
        self.current_monitor_index = monitor_index
        self.target_monitor_index = monitor_index
        self.target_draw_x = float(x)
        self.target_draw_y = float(y)

        if self.last_geometry is None or monitor_changed:
            self._snap_to_position(x, y, monitor_index)

    def _begin_monitor_transition(self, x, y, monitor_index):
        self.monitor_transition_source_monitor = self.current_draw_monitor_index
        self.monitor_transition_target_position = (float(x), float(y))
        self.monitor_transition_target_monitor = monitor_index
        self.monitor_transition_phase = "shrink"
        self.monitor_transition_progress = 0.0
        self.ring.set_motion(0.0, 0.0)

    def _tick_monitor_transition(self, dt):
        if self.monitor_transition_phase is None:
            return False

        self.monitor_transition_progress += dt / max(0.05, self.monitor_transition_duration)
        progress = min(1.0, self.monitor_transition_progress)

        if self.monitor_transition_phase == "shrink":
            eased = 1.0 - (progress * progress)
            self.ring.set_render_presence(max(0.0, eased), eased)
            if progress >= 1.0:
                target_x, target_y = self.monitor_transition_target_position
                target_monitor = self.monitor_transition_target_monitor
                self._force_monitor_jump(target_x, target_y, target_monitor)
                self.monitor_transition_phase = "grow"
                self.monitor_transition_progress = 0.0
                self.ring.set_render_presence(0.0, 0.0)
            return True

        if self.monitor_transition_phase == "grow":
            eased = 1.0 - ((1.0 - progress) * (1.0 - progress))
            self.ring.set_render_presence(eased, eased)
            if progress >= 1.0:
                self.monitor_transition_phase = None
                self.monitor_transition_progress = 0.0
                self.monitor_transition_source_monitor = None
                self.monitor_transition_target_position = None
                self.monitor_transition_target_monitor = None
                self.ring.set_render_presence(1.0, 1.0)
            return True

        self.monitor_transition_phase = None
        self.monitor_transition_source_monitor = None
        self.ring.set_render_presence(1.0, 1.0)
        return False

    def _tick_motion(self, dt):
        if self._tick_monitor_transition(dt):
            return

        if self.current_draw_monitor_index != self.target_monitor_index:
            self.current_draw_monitor_index = self.target_monitor_index
            self.current_draw_x = self.target_draw_x
            self.current_draw_y = self.target_draw_y
            self.ring.set_motion(0.0, 0.0)
            self._apply_current_position()
            return

        delta_x = self.target_draw_x - self.current_draw_x
        delta_y = self.target_draw_y - self.current_draw_y
        distance = math.hypot(delta_x, delta_y)

        if distance < 0.35:
            if distance > 0.0:
                self.current_draw_x = self.target_draw_x
                self.current_draw_y = self.target_draw_y
                self._apply_current_position()
            self.ring.set_motion(0.0, 0.0)
            return

        follow_strength = min(1.0, dt * 9.5)
        move_x = delta_x * follow_strength
        move_y = delta_y * follow_strength
        self.current_draw_x += move_x
        self.current_draw_y += move_y
        self.ring.set_motion(move_x, move_y)
        self._apply_current_position()

    def _reset_visual_transition_state(self):
        self.monitor_transition_phase = None
        self.monitor_transition_progress = 0.0
        self.monitor_transition_source_monitor = None
        self.monitor_transition_target_position = None
        self.monitor_transition_target_monitor = None
        self.ring.set_motion(0.0, 0.0)
        self.ring.set_render_presence(1.0, 1.0)

    @staticmethod
    def _wrap_angle(angle):
        while angle <= -math.pi:
            angle += math.tau
        while angle > math.pi:
            angle -= math.tau
        return angle

    def _showcase_angle_step(self):
        count = max(1, len(self.showcase_entries))
        return math.tau / count

    def _set_showcase_index(self, index, snap=False):
        if not self.showcase_entries:
            self.showcase_selected_index = 0
            self.showcase_current_rotation = 0.0
            self.showcase_target_rotation = 0.0
            return

        self.showcase_selected_index = index % len(self.showcase_entries)
        target_rotation = -self.showcase_selected_index * self._showcase_angle_step()
        self.showcase_target_rotation = target_rotation
        if snap:
            self.showcase_current_rotation = target_rotation

    def _tick_showcase(self, dt):
        if not self.window_showcase_window.isVisible():
            return

        self.showcase_scale_pulse += (0.0 - self.showcase_scale_pulse) * min(1.0, dt * 10.0)

        delta = self._wrap_angle(self.showcase_target_rotation - self.showcase_current_rotation)
        if abs(delta) < 0.0015:
            self.showcase_current_rotation = self.showcase_target_rotation
        else:
            self.showcase_current_rotation = self._wrap_angle(
                self.showcase_current_rotation + (delta * min(1.0, dt * 10.5))
            )

        now = time.monotonic()
        if now - self.showcase_last_preview_refresh_at >= self.showcase_preview_refresh_interval:
            self._refresh_showcase_previews(prioritize_selected=True)

    def _clear_unused_showcase_previews(self):
        valid_ids = {entry.window_id for entry in self.showcase_entries}
        stale_ids = [window_id for window_id in self.showcase_preview_cache if window_id not in valid_ids]
        for window_id in stale_ids:
            self.showcase_preview_cache.pop(window_id, None)

    def _grab_window_preview(self, window_id):
        try:
            target_id = int(str(window_id), 0)
        except (TypeError, ValueError):
            return QPixmap()

        for screen in self.app.screens():
            try:
                pixmap = screen.grabWindow(target_id, 0, 0, -1, -1)
            except Exception:
                continue

            if pixmap is None or pixmap.isNull():
                continue
            if pixmap.width() < 24 or pixmap.height() < 24:
                continue

            return pixmap.scaled(
                480,
                300,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )

        return QPixmap()

    def _refresh_showcase_previews(self, prioritize_selected=False, force=False):
        if not self.showcase_entries:
            self.showcase_preview_cache.clear()
            return

        ordered_entries = list(self.showcase_entries)
        if prioritize_selected and 0 <= self.showcase_selected_index < len(ordered_entries):
            selected_entry = ordered_entries.pop(self.showcase_selected_index)
            ordered_entries.insert(0, selected_entry)

        updated_any = False
        now = time.monotonic()
        for entry in ordered_entries:
            cached = self.showcase_preview_cache.get(entry.window_id)
            if not force and cached and (now - cached["captured_at"]) < self.showcase_preview_refresh_interval:
                continue

            preview = self._grab_window_preview(entry.window_id)
            self.showcase_preview_cache[entry.window_id] = {
                "pixmap": preview,
                "captured_at": now,
            }
            if not preview.isNull():
                updated_any = True

        self._clear_unused_showcase_previews()
        self.showcase_last_preview_refresh_at = now
        if updated_any and self.window_showcase_window.isVisible():
            self.window_showcase_window.update()

    def _begin_dev_workspace_animation(self):
        self.bring_to_front()
        self.ring.set_state("wake", duration=0.8)
        self.dev_mode_animation_active = True
        self.dev_mode_animation_started_at = time.monotonic()
        self.dev_mode_last_spin_at = 0.0
        self.dev_mode_showcase_auto_opened = False

        self.refresh_window_showcase_data()
        if self.showcase_entries:
            self.show_window_showcase(minimize_windows=False, restore_on_hide=False)
            self.dev_mode_showcase_auto_opened = True

    def _tick_dev_workspace_animation(self):
        if not self.dev_mode_animation_active:
            self.ring.set_render_presence(1.0, 1.0)
            return

        elapsed = time.monotonic() - self.dev_mode_animation_started_at
        if elapsed >= self.dev_mode_animation_duration:
            self.dev_mode_animation_active = False
            self.ring.set_render_presence(1.0, 1.0)
            self.ring.set_state("ready")
            if self.dev_mode_showcase_auto_opened and self.window_showcase_window.isVisible():
                self.hide_window_showcase()
            self.dev_mode_showcase_auto_opened = False
            return

        progress = elapsed / max(0.01, self.dev_mode_animation_duration)
        pulse = 1.0 + (0.38 * (math.sin(progress * math.tau * 3.0) * 0.5 + 0.5))
        self.ring.set_render_presence(pulse, 1.0)

        if self.window_showcase_window.isVisible() and (elapsed - self.dev_mode_last_spin_at) >= 0.18:
            self.rotate_window_showcase(1)
            self.dev_mode_last_spin_at = elapsed

    def _run_dev_workspace_setup(self, payload, screens_snapshot):
        spotify_query = (payload or {}).get("spotify_query", "pique anos 80")
        orchestrator = DevWorkspaceOrchestrator(own_pid=os.getpid(), own_caption=self.window_caption)
        orchestrator.run_default_dev_workspace(screens_snapshot, spotify_query=spotify_query)

    def _run_thoughtful_workspace_setup(self):
        orchestrator = ThoughtfulWorkspaceOrchestrator()
        orchestrator.run()

    def stop_dev_workspace(self):
        self.dev_mode_animation_active = False
        self.dev_mode_showcase_auto_opened = False
        self.ring.set_render_presence(1.0, 1.0)
        self.ring.set_state("ready")
        if self.window_showcase_window.isVisible():
            self.hide_window_showcase()
        self.hide_dev_editor()
        self.bring_to_front()

    def start_dev_workspace(self, payload=None):
        self._begin_dev_workspace_animation()
        self.show_dev_editor()
        if self.dev_mode_worker and self.dev_mode_worker.is_alive():
            return

        screens_snapshot = [dict(screen) for screen in self.refresh_screens()]
        self.dev_mode_worker = threading.Thread(
            target=self._run_dev_workspace_setup,
            args=(payload or {}, screens_snapshot),
            daemon=True,
        )
        self.dev_mode_worker.start()

    def start_thoughtful_workspace(self):
        self._begin_dev_workspace_animation()
        if self.dev_mode_worker and self.dev_mode_worker.is_alive():
            return

        self.dev_mode_worker = threading.Thread(
            target=self._run_thoughtful_workspace_setup,
            daemon=True,
        )
        self.dev_mode_worker.start()

    def refresh_window_showcase_data(self):
        self.window_catalog.update_own_caption(self.window_caption)
        entries, reason = self.window_catalog.list_windows(limit=12)
        self.showcase_entries = entries
        self.showcase_message = reason or ""
        self._clear_unused_showcase_previews()

        if not entries:
            self.showcase_selected_index = 0
            self.showcase_current_rotation = 0.0
            self.showcase_target_rotation = 0.0
            return False

        active_index = next((index for index, item in enumerate(entries) if item.is_active), 0)
        self._set_showcase_index(active_index, snap=True)
        self._refresh_showcase_previews(force=True)
        return True

    def _minimize_showcase_windows(self):
        self.showcase_minimized_window_ids = []
        for entry in self.showcase_entries:
            if self.window_catalog.minimize_window(entry.window_id):
                self.showcase_minimized_window_ids.append(entry.window_id)

    def _restore_showcase_windows(self):
        for window_id in self.showcase_minimized_window_ids:
            self.window_catalog.restore_window(window_id)
        self.showcase_minimized_window_ids = []

    def show_window_showcase(self, minimize_windows=True, restore_on_hide=True):
        if self.keep_awake_callback:
            self.keep_awake_callback()
        self.refresh_screens()
        self.refresh_window_showcase_data()
        self.showcase_restore_on_hide = bool(restore_on_hide)
        if minimize_windows:
            self._minimize_showcase_windows()
        else:
            self.showcase_minimized_window_ids = []
        self.showcase_last_preview_refresh_at = 0.0
        self.window_showcase_window.sync_geometry()
        self.window_showcase_window.show()
        self.window_showcase_window.raise_()
        self.window_showcase_window.activateWindow()
        self.window_showcase_window.setFocus(Qt.ActiveWindowFocusReason)

    def hide_window_showcase(self, restore_windows=False):
        should_restore = bool(restore_windows or self.showcase_restore_on_hide)
        self.window_showcase_window.hide()
        self.showcase_restore_on_hide = False
        if should_restore:
            self._restore_showcase_windows()

    def rotate_window_showcase(self, step):
        if self.keep_awake_callback:
            self.keep_awake_callback()
        if not self.window_showcase_window.isVisible():
            self.show_window_showcase()
            if not self.showcase_entries:
                return
        if not self.showcase_entries:
            return
        self.showcase_scale_pulse = 1.0
        self._set_showcase_index(self.showcase_selected_index + int(step))

    def activate_selected_showcase_window(self):
        if not self.showcase_entries:
            self.hide_window_showcase()
            return

        selected = self.showcase_entries[self.showcase_selected_index]
        self._restore_showcase_windows()
        success, message = self.window_catalog.activate_window(selected.window_id)
        if success:
            self.hide_window_showcase(restore_windows=False)
            self.send_to_background()
        else:
            self.showcase_message = message or self.tr("showcase_focus_failed")

    def paint_window_showcase(self, painter, rect):
        pulse_boost = 1.0 + (self.showcase_scale_pulse * 0.18)
        track_center_x = rect.width() / 2.0
        track_center_y = rect.height() * 0.58
        radius_x = min(rect.width() * 0.34, 390.0) * pulse_boost
        radius_y = min(rect.height() * 0.10, 90.0) * (1.0 + (self.showcase_scale_pulse * 0.10))
        card_width = min(rect.width() * 0.26, 320.0) * pulse_boost
        card_height = min(rect.height() * 0.25, 210.0) * pulse_boost

        # Keep the rest of the desktop visible and only light up the disco area.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(18, 44, 58, 34))
        painter.drawEllipse(
            QRectF(
                track_center_x - radius_x - 120,
                track_center_y - radius_y - 110,
                (radius_x + 120) * 2,
                (radius_y + 110) * 2,
            )
        )
        painter.setBrush(QColor(9, 20, 30, 88))
        painter.drawEllipse(
            QRectF(
                track_center_x - radius_x - 36,
                track_center_y - radius_y - 14,
                (radius_x + 36) * 2,
                (radius_y + 14) * 2,
            )
        )

        if not self.showcase_entries:
            empty_font = QFont()
            empty_font.setPointSize(16)
            empty_font.setBold(True)
            painter.setFont(empty_font)
            painter.setPen(QColor(220, 236, 244, 220))
            painter.drawText(
                QRectF(track_center_x - 220, track_center_y - 64, 440, 128),
                Qt.AlignCenter | Qt.TextWordWrap,
                self.showcase_message or self.tr("showcase_empty"),
            )
            return

        painter.setBrush(QColor(28, 74, 92, 44))
        painter.drawEllipse(
            QRectF(
                track_center_x - radius_x - 42,
                track_center_y - radius_y - 18,
                (radius_x + 42) * 2,
                (radius_y + 18) * 2,
            )
        )
        painter.setBrush(QColor(63, 212, 165, 18))
        painter.drawEllipse(
            QRectF(
                track_center_x - 108,
                track_center_y - 92,
                216,
                184,
            )
        )

        render_queue = []
        angle_step = self._showcase_angle_step()
        for index, entry in enumerate(self.showcase_entries):
            angle = self._wrap_angle(self.showcase_current_rotation + (index * angle_step))
            depth = (math.cos(angle) + 1.0) / 2.0
            scale = 0.56 + (depth * 0.60)
            alpha = 0.22 + (depth * 0.78)
            center_x = track_center_x + (math.sin(angle) * radius_x)
            center_y = track_center_y - (radius_y * 0.55) + (depth * radius_y * 1.2)
            render_queue.append((depth, index, entry, scale, alpha, center_x, center_y))

        render_queue.sort(key=lambda item: item[0])
        for depth, index, entry, scale, alpha, center_x, center_y in render_queue:
            width = card_width * scale
            height = card_height * scale
            card_rect = QRectF(center_x - (width / 2.0), center_y - (height / 2.0), width, height)
            shadow_rect = QRectF(card_rect.x() + 10, card_rect.y() + 16, card_rect.width(), card_rect.height())
            shadow_alpha = int(40 + (depth * 90))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, shadow_alpha))
            painter.drawRoundedRect(shadow_rect, 26, 26)

            base_fill = QColor(10, 19, 29, int(155 * alpha))
            painter.setBrush(base_fill)
            border_color = QColor(116, 215, 188, int(245 * alpha)) if index == self.showcase_selected_index else QColor(105, 148, 175, int(165 * alpha))
            painter.setPen(QPen(border_color, 2.2))
            painter.drawRoundedRect(card_rect, 24, 24)

            header_rect = QRectF(card_rect.x(), card_rect.y(), card_rect.width(), max(32.0, card_rect.height() * 0.20))
            preview_rect = QRectF(
                card_rect.x() + 10,
                header_rect.y() + header_rect.height() + 8,
                card_rect.width() - 20,
                card_rect.height() - header_rect.height() - 18,
            )
            header_fill = QColor(63, 212, 165, int(78 * alpha)) if index == self.showcase_selected_index else QColor(69, 114, 151, int(56 * alpha))
            painter.setPen(Qt.NoPen)
            painter.setBrush(header_fill)
            painter.drawRoundedRect(header_rect, 24, 24)
            painter.fillRect(QRectF(header_rect.x(), header_rect.y() + header_rect.height() / 2.0, header_rect.width(), header_rect.height() / 2.0), header_fill)

            preview_fill = QColor(5, 11, 18, int(205 * alpha))
            painter.setBrush(preview_fill)
            painter.drawRoundedRect(preview_rect, 18, 18)

            cached_preview = self.showcase_preview_cache.get(entry.window_id, {})
            pixmap = cached_preview.get("pixmap")
            if isinstance(pixmap, QPixmap) and not pixmap.isNull():
                preview_path = QPainterPath()
                preview_path.addRoundedRect(preview_rect, 18, 18)
                painter.save()
                painter.setClipPath(preview_path)
                painter.setOpacity(alpha * 0.96)
                painter.drawPixmap(preview_rect, pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))
                painter.restore()

                painter.setPen(QPen(QColor(255, 255, 255, int(26 * alpha)), 1.0))
                painter.drawLine(
                    QPointF(preview_rect.left(), preview_rect.top() + preview_rect.height() * 0.52),
                    QPointF(preview_rect.right(), preview_rect.top() + preview_rect.height() * 0.52),
                )
            else:
                painter.setBrush(QColor(13, 26, 38, int(185 * alpha)))
                painter.drawRoundedRect(preview_rect, 18, 18)
                painter.setPen(QColor(168, 205, 223, int(120 * alpha)))
                painter.drawText(
                    preview_rect.adjusted(14, 14, -14, -14),
                    Qt.AlignCenter | Qt.TextWordWrap,
                    entry.app_name,
                )

            title_font = QFont()
            title_font.setPointSizeF(max(9.0, 12.0 * scale))
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(QColor(241, 249, 255, int(255 * alpha)))
            painter.drawText(
                QRectF(
                    header_rect.x() + 18,
                    header_rect.y() + 9,
                    header_rect.width() - 36,
                    header_rect.height() - 12,
                ),
                Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
                entry.title,
            )

            subtitle_font = QFont()
            subtitle_font.setPointSizeF(max(8.0, 10.0 * scale))
            painter.setFont(subtitle_font)
            painter.setPen(QColor(176, 210, 225, int(220 * alpha)))
            subtitle = entry.app_name
            if entry.is_active:
                subtitle = f"{subtitle}  {self.tr('showcase_active')}"
            painter.drawText(
                QRectF(
                    preview_rect.x() + 12,
                    preview_rect.bottom() - 34,
                    preview_rect.width() - 24,
                    22,
                ),
                Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter,
                subtitle,
            )

        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#f3fbff"))
        painter.drawText(
            QRectF(track_center_x - 120, track_center_y - radius_y - card_height * 0.95, 240, 28),
            Qt.AlignCenter | Qt.AlignVCenter,
            self.tr("showcase_title"),
        )

        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(190, 221, 235, 210))
        status_line = self.tr("showcase_status")
        if self.showcase_message:
            status_line = self.showcase_message
        painter.drawText(
            QRectF(track_center_x - 260, track_center_y + card_height * 0.72, 520, 22),
            Qt.AlignCenter | Qt.AlignVCenter,
            status_line,
        )

    def prepare_ring_for_paint(self, width, height):
        self.ring.resize(width, height)
        if self.window_positioning_limited and self.ring_center is not None:
            self.ring.set_center(*self.ring_center)

    def position_quick_input(self):
        if not hasattr(self, "root") or self.root is None or not hasattr(self, "quick_input_window"):
            return
        # During a monitor transition, current_monitor_index already points
        # to the destination while the overlay is still on its source
        # monitor. Use the monitor currently occupied by the overlay instead.
        monitor_index = getattr(self, "current_draw_monitor_index", self.current_monitor_index)
        screen, _safe_index = self._get_screen(monitor_index)
        x = screen["x"] + (screen["width"] - self.quick_input_width) // 2
        y = screen["y"] + screen["height"] - self.quick_input_height - self.window_margin
        self.quick_input_window.setGeometry(x, y, self.quick_input_width, self.quick_input_height)

    def position_dev_editor(self):
        if not hasattr(self, "dev_editor_window") or self.dev_editor_window is None:
            return
        screen, _safe_index = self._get_screen(0)
        margin = max(20, self.window_margin - 8)
        width = max(760, screen["width"] - (margin * 2))
        height = max(520, screen["height"] - (margin * 2))
        x = screen["x"] + margin
        y = screen["y"] + margin
        self.dev_editor_window.setGeometry(x, y, width, height)

    def move_external_window(self, payload):
        payload = payload or {}
        target_query = str(payload.get("target") or "active").strip().lower()
        windows, reason = self.window_catalog.list_windows(limit=40)
        if not windows:
            self.set_response_text(reason or self.tr("window_move_failed"))
            return

        selected = None
        if target_query in {"active", "current", "foreground", "janela ativa", "janela atual"}:
            selected = next((item for item in windows if item.is_active), None)
        else:
            for item in windows:
                haystack = f"{item.app_name} {item.title}".lower()
                if target_query in haystack:
                    selected = item
                    break
        if selected is None:
            self.set_response_text(self.tr("window_move_target_missing", target=target_query))
            return

        monitor_value = payload.get("monitor", "current")
        monitor_index = self._resolve_monitor_index(monitor_value)
        screen, _safe_index = self._get_screen(monitor_index)
        position = payload.get("position", "current")
        if position == "current":
            x = screen["x"] + self.window_margin
            y = screen["y"] + self.window_margin
        else:
            x, y = self._window_target_location(position, screen, selected.window_id)

        rect = self.window_catalog.get_window_rect(selected.window_id)
        if not rect:
            self.set_response_text(self.tr("window_move_failed"))
            return

        left, top, right, bottom = rect
        return_monitor = self.current_draw_monitor_index
        window_width = right - left
        title_bar_center_x = left + (window_width / 2.0)
        title_bar_center_y = top + min(30.0, max(18.0, (bottom - top) * 0.10))
        approach_x = title_bar_center_x - (self.window_size_x / 2.0)
        approach_y = title_bar_center_y - (self.window_size_y / 2.0)
        self.external_window_drag = {
            "window_id": selected.window_id,
            "start_x": float(left),
            "start_y": float(top),
            "target_x": float(x),
            "target_y": float(y),
            "return_x": float(self.current_draw_x),
            "return_y": float(self.current_draw_y),
            "return_monitor": return_monitor,
            "approach_x": approach_x,
            "approach_y": approach_y,
            "target_monitor": monitor_index,
            "phase": "approach",
            "elapsed": 0.0,
            "approach_duration": 0.95,
            "drag_duration": 1.25,
            "return_duration": 0.85,
        }
        self._animate_overlay_to(approach_x, approach_y, monitor_index)

    def _animate_overlay_to(self, x, y, monitor_index):
        self.current_monitor_index = monitor_index
        self.target_monitor_index = monitor_index
        if monitor_index != self.current_draw_monitor_index:
            self._begin_monitor_transition(x, y, monitor_index)
        else:
            self._set_target_position(x, y, monitor_index)

    def _tick_external_window_drag(self, dt):
        drag = self.external_window_drag
        if not drag:
            return

        drag["elapsed"] += dt
        if drag["phase"] == "approach":
            ready = (
                self.monitor_transition_phase is None
                and abs(self.current_draw_x - drag["approach_x"]) < 3.0
                and abs(self.current_draw_y - drag["approach_y"]) < 3.0
            )
            if ready or drag["elapsed"] >= drag["approach_duration"] + 1.2:
                drag["phase"] = "drag"
                drag["elapsed"] = 0.0
            return

        if drag["phase"] == "drag":
            progress = min(1.0, drag["elapsed"] / drag["drag_duration"])
            eased = progress * progress * (3.0 - (2.0 * progress))
            x = drag["start_x"] + ((drag["target_x"] - drag["start_x"]) * eased)
            y = drag["start_y"] + ((drag["target_y"] - drag["start_y"]) * eased)
            success, _reason = self.window_catalog.move_window(drag["window_id"], x, y)
            if success:
                rect = self.window_catalog.get_window_rect(drag["window_id"])
                if rect:
                    left, top, right, bottom = rect
                    title_bar_center_x = left + ((right - left) / 2.0)
                    title_bar_center_y = top + min(
                        30.0,
                        max(18.0, (bottom - top) * 0.10),
                    )
                    follow_monitor = self._monitor_index_for_point(
                        title_bar_center_x,
                        title_bar_center_y,
                        drag["target_monitor"],
                    )
                    self._snap_to_position(
                        title_bar_center_x - (self.window_size_x / 2.0),
                        title_bar_center_y - (self.window_size_y / 2.0),
                        follow_monitor,
                    )
                    self.position_quick_input()
            if not success or progress >= 1.0:
                drag["phase"] = "return"
                drag["elapsed"] = 0.0
                self._animate_overlay_to(
                    drag["return_x"],
                    drag["return_y"],
                    drag["return_monitor"],
                )
            return

        if drag["phase"] == "return":
            ready = (
                self.monitor_transition_phase is None
                and abs(self.current_draw_x - drag["return_x"]) < 3.0
                and abs(self.current_draw_y - drag["return_y"]) < 3.0
            )
            if ready or drag["elapsed"] >= drag["return_duration"] + 1.2:
                self.external_window_drag = None

    def change_external_window_state(self, payload):
        payload = payload or {}
        target_query = str(payload.get("target") or "active").strip().lower()
        windows, reason = self.window_catalog.list_windows(limit=40)
        if not windows:
            self.set_response_text(reason or self.tr("window_state_failed"))
            return

        selected = None
        if target_query in {"active", "current", "foreground", "janela ativa", "janela atual"}:
            selected = next((item for item in windows if item.is_active), None)
        else:
            for item in windows:
                if target_query in f"{item.app_name} {item.title}".lower():
                    selected = item
                    break
        if selected is None:
            self.set_response_text(self.tr("window_move_target_missing", target=target_query))
            return

        rect = self.window_catalog.get_window_rect(selected.window_id)
        if not rect:
            self.set_response_text(self.tr("window_state_failed"))
            return
        control_point = self.window_catalog.get_window_control_point(
            selected.window_id,
            payload.get("action", "maximize"),
        )
        if not control_point:
            self.set_response_text(self.tr("window_state_failed"))
            return
        title_bar_center_x, title_bar_center_y = control_point
        self.external_window_action = {
            "window_id": selected.window_id,
            "action": payload.get("action", "restore"),
            "return_x": float(self.current_draw_x),
            "return_y": float(self.current_draw_y),
            "return_monitor": self.current_draw_monitor_index,
            "phase": "approach",
            "elapsed": 0.0,
            "approach_x": title_bar_center_x - (self.window_size_x / 2.0),
            "approach_y": title_bar_center_y - (self.window_size_y / 2.0),
        }
        monitor_index = self._monitor_index_for_point(
            title_bar_center_x,
            title_bar_center_y,
            self.current_draw_monitor_index,
        )
        self._animate_overlay_to(
            self.external_window_action["approach_x"],
            self.external_window_action["approach_y"],
            monitor_index,
        )

    def _tick_external_window_action(self, dt):
        action = self.external_window_action
        if not action:
            return
        action["elapsed"] += dt
        if action["phase"] == "approach":
            ready = (
                self.monitor_transition_phase is None
                and abs(self.current_draw_x - action["approach_x"]) < 3.0
                and abs(self.current_draw_y - action["approach_y"]) < 3.0
            )
            if ready or action["elapsed"] >= 2.2:
                action["phase"] = "press"
                action["elapsed"] = 0.0
            return

        if action["phase"] == "press":
            if action["elapsed"] >= 0.28:
                self.window_catalog.set_window_state(
                    action["window_id"],
                    action["action"],
                )
                action["phase"] = "return"
                action["elapsed"] = 0.0
                self._animate_overlay_to(
                    action["return_x"],
                    action["return_y"],
                    action["return_monitor"],
                )
            return

        if action["phase"] == "return":
            ready = (
                self.monitor_transition_phase is None
                and abs(self.current_draw_x - action["return_x"]) < 3.0
                and abs(self.current_draw_y - action["return_y"]) < 3.0
            )
            if ready or action["elapsed"] >= 2.0:
                self.external_window_action = None

    def _monitor_index_for_point(self, x, y, fallback=0):
        for index, screen in enumerate(self.screens):
            if (
                screen["x"] <= x < screen["x"] + screen["width"]
                and screen["y"] <= y < screen["y"] + screen["height"]
            ):
                return index
        return fallback

    def _window_target_location(self, position, screen, window_id):
        try:
            import win32gui
            left, top, right, bottom = win32gui.GetWindowRect(int(str(window_id), 0))
            width = max(120, right - left)
            height = max(80, bottom - top)
        except Exception:
            width, height = 900, 650

        margin = max(24, self.window_margin)
        x_min = screen["x"] + margin
        y_min = screen["y"] + margin
        x_max = screen["x"] + screen["width"] - width - margin
        y_max = screen["y"] + screen["height"] - height - margin
        x_center = screen["x"] + (screen["width"] - width) // 2
        y_center = screen["y"] + (screen["height"] - height) // 2
        return {
            "top_left": (x_min, y_min),
            "top": (x_center, y_min),
            "top_right": (x_max, y_min),
            "left": (x_min, y_center),
            "center": (x_center, y_center),
            "right": (x_max, y_center),
            "bottom_left": (x_min, y_max),
            "bottom": (x_center, y_max),
            "bottom_right": (x_max, y_max),
        }.get(position, (x_center, y_center))

    def show_dev_editor(self):
        self.position_dev_editor()
        self.dev_editor_window.show()
        self.dev_editor_window.raise_()
        self.dev_editor_window.activateWindow()
        self.dev_editor_window.editor.setFocus()

    def hide_dev_editor(self):
        if hasattr(self, "dev_editor_window") and self.dev_editor_window is not None:
            self.dev_editor_window.hide()

    def handle_quick_input_keypress(self, _event=None):
        if self.keep_awake_callback:
            self.keep_awake_callback()

    def show_quick_input(self):
        if self.keep_awake_callback:
            self.keep_awake_callback()
        self.position_quick_input()
        self.position_dev_editor()
        if self.is_windows:
            self.quick_input_window.showNormal()
        self.quick_input_window.show()
        self.quick_input_window.raise_()
        self.quick_input_window.activateWindow()
        self.quick_input_window.setFocus(Qt.ActiveWindowFocusReason)
        self.quick_input_window.entry.setFocus(Qt.ActiveWindowFocusReason)
        self.quick_input_window.entry.selectAll()

    def hide_quick_input(self):
        self.quick_input_window.hide()

    def get_settings_values(self):
        return self.settings_values_callback()

    def show_settings(self):
        if self.keep_awake_callback:
            self.keep_awake_callback()
        self.settings_window.load_values()
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def apply_runtime_settings(self):
        self.language = get_env("LANGUAGE", "en")
        self.window_size_x = get_env("WINDOW_WIDTH", 260, int)
        self.window_size_y = get_env("WINDOW_HEIGHT", 260, int)
        self.base_window_size_x = self.window_size_x
        self.base_window_size_y = self.window_size_y
        self.window_caption = "maya"
        self.overlay_window_title = self.tr("overlay_window_title", caption=self.window_caption)
        self.showcase_window_title = self.tr("showcase_window_title", caption=self.window_caption)
        self.quick_input_window_title = self.tr("quick_input_window_title", caption=self.window_caption)
        self.settings_window_title = self.tr("settings_window_caption", caption=self.window_caption)
        self.window_margin = get_env("WINDOW_MARGIN", 32, int)
        self.quick_input_width = get_env("QUICK_INPUT_WIDTH", 420, int)
        self.quick_input_height = max(210, get_env("QUICK_INPUT_HEIGHT", 210, int))
        self.initial_position = get_env("INITIAL_POSITION", "top_right")
        self.initial_monitor = max(1, get_env("INITIAL_MONITOR", 2, int))
        self.initial_scale = get_env("INITIAL_SCALE", 0.5, float)
        self.window_positioning_limited = self.is_linux and os.getenv("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
        self.screens = self._get_screens()
        self.root.setWindowTitle(self.overlay_window_title)
        self.window_showcase_window.setWindowTitle(self.showcase_window_title)
        self.quick_input_window.setWindowTitle(self.quick_input_window_title)
        self.settings_window.setWindowTitle(self.settings_window_title)
        self.window_catalog.update_own_caption(self.window_caption)
        self.quick_input_window.retranslate_ui()
        self.dev_editor_window.retranslate_ui()
        self.settings_window.retranslate_ui()
        self.root._update_mask()
        self.ring.default_radius = get_env("UI_RING_RADIUS", 72, int)
        self.ring.default_thickness = get_env("UI_RING_THICKNESS", 18, int)
        self._apply_ring_palette_from_settings()
        self.ring.set_scale(self.scale_factor)
        self.set_scale("set", self.initial_scale)
        x, y = self._compute_window_location(self.initial_position, self.initial_monitor - 1)
        self._snap_to_position(x, y, self.current_monitor_index)
        self.position_quick_input()
        self.position_dev_editor()

    def set_voice_status(self, status):
        self.voice_status = status
        if hasattr(self, "quick_input_window"):
            self.quick_input_window.set_status(status)
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
        if hasattr(self, "quick_input_window"):
            self.quick_input_window.set_response(text)
        self.ring.set_state("speaking", duration=0.6)

    def trigger_wake(self):
        self.ring.set_state("wake", duration=0.45)
        self.bring_to_front()

    def move_overlay(self, position_name, monitor_index):
        self.refresh_screens()
        # bring_to_front resets stale animation state, so it must happen
        # before a new cross-monitor transition is created.
        self.bring_to_front()
        if not position_name or position_name == "current":
            position_name = self.current_position_name
        previous_monitor_index = self.current_monitor_index
        x, y = self._compute_window_location(position_name, monitor_index)
        if self.current_monitor_index != previous_monitor_index:
            self._begin_monitor_transition(x, y, self.current_monitor_index)
        else:
            self._set_target_position(x, y, self.current_monitor_index)
        self.position_quick_input()
        self.position_dev_editor()

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
        x, y = self._compute_window_location(self.current_position_name, self.current_monitor_index)
        self._snap_to_position(x, y, self.current_monitor_index)
        self.position_quick_input()
        self.position_dev_editor()

    def send_to_background(self):
        self.is_backgrounded = True
        self._reset_visual_transition_state()
        self.hide_window_showcase()
        self.hide_quick_input()
        self.hide_dev_editor()
        self.root.hide()

    def hide_overlay(self):
        self.send_to_background()

    def bring_to_front(self):
        self.is_backgrounded = False
        self._reset_visual_transition_state()
        self._apply_current_position()
        if self.window_positioning_limited:
            self.root.show()
        else:
            self.root.show()
        if not self.window_positioning_limited:
            self.root.raise_()
        self.position_quick_input()
        self.position_dev_editor()

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
            elif event == "app_show_settings":
                self.show_settings()
            elif event == "app_show_window_showcase":
                self.show_window_showcase()
            elif event == "app_hide_window_showcase":
                self.hide_window_showcase()
            elif event == "app_rotate_window_showcase":
                payload = value or {}
                self.rotate_window_showcase(payload.get("step", 1))
            elif event == "app_start_dev_workspace":
                self.start_dev_workspace(value or {})
            elif event == "app_start_thoughtful_workspace":
                self.start_thoughtful_workspace()
            elif event == "app_stop_dev_workspace":
                launcher = AppLauncher()
                for alias in ("spotify", "firefox"):
                    app_key = launcher.resolve_alias(alias)
                    if app_key:
                        launcher.close(app_key)
                self.stop_dev_workspace()
            elif event == "app_move":
                monitor_value = value.get("monitor", 1)
                self.move_overlay(
                    value.get("position", "current"),
                    self._resolve_monitor_index(monitor_value),
                )
            elif event == "app_move_window":
                self.move_external_window(value)
            elif event == "app_window_state":
                self.change_external_window_state(value)
            elif event == "app_scale":
                self.set_scale(
                    value.get("mode", "set"),
                    float(value.get("value", 1.0)),
                )
            elif event == "exit":
                self.app.quit()

    def update(self):
        self.handle_events()
        self._tick_motion(1 / 60)
        self._tick_external_window_drag(1 / 60)
        self._tick_external_window_action(1 / 60)
        self._tick_dev_workspace_animation()
        self._tick_showcase(1 / 60)
        self.ring.update(1 / 60)
        if hasattr(self, "root") and self.root is not None:
            self.root.update()
        if self.window_showcase_window.isVisible():
            self.window_showcase_window.update()

        if self.periodic_callback:
            self.periodic_callback(1 / 60)

    def run(self):
        self.timer.start(16)
        self.app.exec()

    def get_fps(self):
        return "qt"
