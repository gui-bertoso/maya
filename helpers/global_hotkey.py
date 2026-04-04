import sys
import threading


class GlobalHotkeyListener:
    def __init__(self):
        self.thread = None
        self.is_running = False
        self.hotkey_registered = False

    def start_ctrl_m(self, callback):
        if self.thread and self.thread.is_alive():
            return True

        if sys.platform != "win32":
            return False

        self.thread = threading.Thread(
            target=self._run_ctrl_m_listener,
            args=(callback,),
            daemon=True,
        )
        self.thread.start()
        return True

    def _run_ctrl_m_listener(self, callback):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        MOD_CONTROL = 0x0002
        VK_M = 0x4D
        HOTKEY_ID = 1
        WM_HOTKEY = 0x0312

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("pt_x", ctypes.c_long),
                ("pt_y", ctypes.c_long),
            ]

        self.is_running = True
        thread_id = kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL, VK_M):
            self.is_running = False
            return

        self.hotkey_registered = True
        self._thread_id = thread_id

        msg = MSG()
        try:
            while self.is_running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    callback()
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self.hotkey_registered = False
            self.is_running = False

    def stop(self):
        if sys.platform != "win32":
            self.is_running = False
            return

        if not getattr(self, "_thread_id", None):
            self.is_running = False
            return

        import ctypes

        WM_QUIT = 0x0012
        self.is_running = False
        ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
