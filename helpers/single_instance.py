import ctypes
import sys


ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\MayaPersonalAssistant"


class SingleInstance:
    """Keep one Maya process per Windows session."""

    def __init__(self, mutex_name=MUTEX_NAME):
        self.mutex_name = mutex_name
        self.handle = None

    def acquire(self):
        if not sys.platform.startswith("win"):
            return True

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        create_mutex.restype = ctypes.c_void_p

        ctypes.set_last_error(0)
        self.handle = create_mutex(None, False, self.mutex_name)
        if not self.handle:
            return True
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS

    @staticmethod
    def show_existing_window(caption="maya"):
        if not sys.platform.startswith("win"):
            return False

        try:
            user32 = ctypes.windll.user32
            window = user32.FindWindowW(None, caption)
            if not window:
                return False
            user32.ShowWindow(window, 9)
            user32.SetForegroundWindow(window)
            return True
        except Exception:
            return False
