import math
import os
import sys
import threading
import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from helpers.config import get_env, get_env_fields, get_env_values
from helpers.dev_workspace import DevWorkspaceOrchestrator
from helpers.thoughtful_workspace import ThoughtfulWorkspaceOrchestrator
from helpers.window_showcase import WindowShowcaseBackend


def _overlay_window_flags(is_linux=False, interactive=False):
    flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint

    if is_linux and hasattr(Qt, "BypassWindowManagerHint"):
        flags |= Qt.BypassWindowManagerHint

    if is_linux and not interactive and hasattr(Qt, "WindowDoesNotAcceptFocus"):
        flags |= Qt.WindowDoesNotAcceptFocus

    return flags


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
        self.motion_x = 0.0
        self.motion_y = 0.0
        self.motion_speed = 0.0
        self.render_scale = 1.0
        self.render_alpha = 1.0

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
        flags = _overlay_window_flags(is_linux=self.renderer.is_linux, interactive=False)
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
        flags = _overlay_window_flags(is_linux=self.renderer.is_linux, interactive=True)
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
        flags = _overlay_window_flags(is_linux=self.renderer.is_linux, interactive=True)
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


class SettingsWindow(QWidget):
    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer
        self.inputs = {}

        self.setWindowTitle("Maya User Settings")
        self.resize(680, 760)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        title = QLabel("Maya User Settings")
        title.setObjectName("settingsTitle")
        subtitle = QLabel("Edit `.env` values here and apply changes immediately.")
        subtitle.setObjectName("settingsSubtitle")
        subtitle.setWordWrap(True)
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        self.sections_layout = QVBoxLayout(scroll_content)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(14)

        current_category = None
        current_form = None
        for field in get_env_fields():
            if field.category != current_category:
                section = QFrame()
                section.setObjectName("settingsSection")
                section_layout = QVBoxLayout(section)
                section_layout.setContentsMargins(18, 18, 18, 18)
                section_layout.setSpacing(10)

                section_title = QLabel(field.category)
                section_title.setObjectName("settingsSectionTitle")
                section_layout.addWidget(section_title)

                current_form = QFormLayout()
                current_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
                current_form.setFormAlignment(Qt.AlignTop)
                current_form.setHorizontalSpacing(20)
                current_form.setVerticalSpacing(12)
                section_layout.addLayout(current_form)
                self.sections_layout.addWidget(section)
                current_category = field.category

            label = QLabel(field.label or field.key.replace("_", " ").title())
            label.setObjectName("settingsLabel")
            label.setToolTip(field.help_text)

            if field.options:
                control = QComboBox()
                control.addItems(list(field.options))
                control.setEditable(False)
            else:
                control = QLineEdit()
                control.setPlaceholderText(field.default)

            control.setObjectName("settingsInput")
            control.setToolTip(field.help_text)
            self.inputs[field.key] = control

            field_layout = QVBoxLayout()
            field_layout.setSpacing(4)
            field_layout.addWidget(control)
            if field.help_text:
                help_label = QLabel(field.help_text)
                help_label.setObjectName("settingsHelp")
                help_label.setWordWrap(True)
                field_layout.addWidget(help_label)

            current_form.addRow(label, field_layout)

        self.sections_layout.addStretch(1)
        scroll_area.setWidget(scroll_content)
        root_layout.addWidget(scroll_area, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.status_label = QLabel("")
        self.status_label.setObjectName("settingsStatus")
        actions.addWidget(self.status_label, 1)

        refresh_button = QPushButton("Reload")
        refresh_button.clicked.connect(self.load_values)
        apply_button = QPushButton("Apply")
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self.apply_changes)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.hide)

        actions.addWidget(refresh_button)
        actions.addWidget(apply_button)
        actions.addWidget(close_button)
        root_layout.addLayout(actions)

        self.setStyleSheet(
            """
            QWidget {
                background: #0c1217;
                color: #eef4fa;
                font-size: 14px;
            }
            QFrame#settingsSection {
                background: rgba(17, 26, 34, 228);
                border: 1px solid rgba(110, 171, 207, 70);
                border-radius: 18px;
            }
            QLabel#settingsTitle {
                font-size: 28px;
                font-weight: 700;
                color: #f7fbff;
            }
            QLabel#settingsSubtitle {
                color: rgba(227, 237, 246, 170);
            }
            QLabel#settingsSectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #8ee0ff;
            }
            QLabel#settingsLabel {
                font-weight: 600;
                padding-top: 6px;
            }
            QLabel#settingsHelp {
                color: rgba(214, 227, 239, 145);
                font-size: 12px;
            }
            QLabel#settingsStatus {
                color: #9edab1;
            }
            QLineEdit, QComboBox {
                min-height: 38px;
                border-radius: 12px;
                border: 1px solid rgba(124, 176, 212, 80);
                background: rgba(6, 11, 16, 225);
                padding: 0 12px;
                selection-background-color: rgba(94, 175, 219, 120);
            }
            QScrollArea {
                background: transparent;
            }
            QPushButton {
                min-height: 38px;
                border-radius: 12px;
                border: 1px solid rgba(124, 176, 212, 80);
                background: rgba(21, 33, 43, 240);
                padding: 0 16px;
            }
            QPushButton#primaryButton {
                background: #78c6a3;
                color: #092114;
                border-color: #78c6a3;
                font-weight: 700;
            }
            """
        )

        self.hide()

    def _set_control_value(self, control, value):
        text = "" if value is None else str(value)
        if isinstance(control, QComboBox):
            index = control.findText(text, Qt.MatchFixedString)
            if index >= 0:
                control.setCurrentIndex(index)
            elif control.count() > 0:
                control.setCurrentIndex(0)
        else:
            control.setText(text)

    def _get_control_value(self, control):
        if isinstance(control, QComboBox):
            return control.currentText().strip()
        return control.text().strip()

    def load_values(self):
        values = self.renderer.get_settings_values()
        for key, control in self.inputs.items():
            self._set_control_value(control, values.get(key, ""))
        self.status_label.setText("")

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
        self.apply_settings_callback = settings_apply_callback or (lambda _values: (False, "Settings apply callback not configured."))
        self.settings_values_callback = settings_values_callback or get_env_values

        self.window_size_x = get_env("WINDOW_WIDTH", 260, int)
        self.window_size_y = get_env("WINDOW_HEIGHT", 260, int)
        self.base_window_size_x = self.window_size_x
        self.base_window_size_y = self.window_size_y
        self.window_caption = get_env("WINDOW_CAPTION", "maya")
        self.overlay_window_title = f"{self.window_caption} overlay"
        self.showcase_window_title = f"{self.window_caption} showcase"
        self.quick_input_window_title = f"{self.window_caption} quick input"
        self.settings_window_title = f"{self.window_caption} settings"
        self.window_margin = get_env("WINDOW_MARGIN", 32, int)
        self.quick_input_width = get_env("QUICK_INPUT_WIDTH", 420, int)
        self.quick_input_height = get_env("QUICK_INPUT_HEIGHT", 92, int)
        self.scale_factor = 1.0
        self.initial_position = get_env("INITIAL_POSITION", "top_right")
        self.initial_monitor = max(1, get_env("INITIAL_MONITOR", 2, int))
        self.initial_scale = get_env("INITIAL_SCALE", 0.5, float)
        self.is_linux = sys.platform.startswith("linux")
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
        self.ring.set_state("idle")

        self.root = OverlayWidget(self)
        self.root.setWindowTitle(self.overlay_window_title)
        self.window_catalog = WindowShowcaseBackend(own_pid=os.getpid(), own_caption=self.window_caption)
        self.window_showcase_window = WindowShowcaseWidget(self)
        self.quick_input_window = QuickInputWidget(self)
        self.settings_window = SettingsWindow(self)
        self.window_showcase_window.setWindowTitle(self.showcase_window_title)
        self.quick_input_window.setWindowTitle(self.quick_input_window_title)
        self.settings_window.setWindowTitle(self.settings_window_title)
        _apply_windows_overlay_style(self.root)
        _apply_windows_overlay_style(self.quick_input_window)
        _apply_windows_overlay_style(self.window_showcase_window)

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
            self.show_window_showcase()
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
        self.bring_to_front()

    def start_dev_workspace(self, payload=None):
        self._begin_dev_workspace_animation()
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
            self.showcase_message = message or "i could not focus that window."

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
                self.showcase_message or "No open windows available for the showcase.",
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
                subtitle = f"{subtitle}  ACTIVE"
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
            "window disco",
        )

        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(190, 221, 235, 210))
        status_line = "left/right or mouse wheel to rotate. enter to focus. esc to close."
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
        self.window_size_x = get_env("WINDOW_WIDTH", 260, int)
        self.window_size_y = get_env("WINDOW_HEIGHT", 260, int)
        self.base_window_size_x = self.window_size_x
        self.base_window_size_y = self.window_size_y
        self.window_caption = get_env("WINDOW_CAPTION", "maya")
        self.overlay_window_title = f"{self.window_caption} overlay"
        self.showcase_window_title = f"{self.window_caption} showcase"
        self.quick_input_window_title = f"{self.window_caption} quick input"
        self.settings_window_title = f"{self.window_caption} settings"
        self.window_margin = get_env("WINDOW_MARGIN", 32, int)
        self.quick_input_width = get_env("QUICK_INPUT_WIDTH", 420, int)
        self.quick_input_height = get_env("QUICK_INPUT_HEIGHT", 92, int)
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
        self.root._update_mask()
        self.ring.default_radius = get_env("UI_RING_RADIUS", 72, int)
        self.ring.default_thickness = get_env("UI_RING_THICKNESS", 18, int)
        self.ring.set_scale(self.scale_factor)
        self.set_scale("set", self.initial_scale)
        x, y = self._compute_window_location(self.initial_position, self.initial_monitor - 1)
        self._snap_to_position(x, y, self.current_monitor_index)
        self.position_quick_input()

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
        self.refresh_screens()
        if not position_name or position_name == "current":
            position_name = self.current_position_name
        previous_monitor_index = self.current_monitor_index
        x, y = self._compute_window_location(position_name, monitor_index)
        if self.current_monitor_index != previous_monitor_index:
            self._begin_monitor_transition(x, y, self.current_monitor_index)
        else:
            self._set_target_position(x, y, self.current_monitor_index)
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
        x, y = self._compute_window_location(self.current_position_name, self.current_monitor_index)
        self._snap_to_position(x, y, self.current_monitor_index)
        self.position_quick_input()

    def send_to_background(self):
        self.is_backgrounded = True
        self._reset_visual_transition_state()
        self.hide_window_showcase()
        self.hide_quick_input()
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
                for alias in ("spotify", "firefox", "vscode"):
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
