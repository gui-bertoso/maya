import threading
import sys
import time


class GlobalHotkeyListener:
    def __init__(self):
        self.thread = None
        self.is_running = False
        self.hotkey_registered = False
        self.last_error = None
        self._listener = None
        self._startup_success = False

    def start_pgdown_end(self, callback):
        if self.thread and self.thread.is_alive():
            return True

        self.last_error = None
        self._startup_success = False
        startup_event = threading.Event()
        self.thread = threading.Thread(
            target=self._run_pgdown_end_listener,
            args=(callback, startup_event),
            daemon=True,
        )
        self.thread.start()
        startup_event.wait(2.0)
        return self._startup_success

    def _run_windows_hotkey_listener(self, callback, startup_event):
        try:
            import ctypes

            user32 = ctypes.windll.user32
            VK_NEXT = 0x22
            VK_END = 0x23
            hotkey_latched = False

            self.is_running = True
            self.hotkey_registered = True
            self._startup_success = True
            startup_event.set()

            while self.is_running:
                pgdown_pressed = bool(user32.GetAsyncKeyState(VK_NEXT) & 0x8000)
                end_pressed = bool(user32.GetAsyncKeyState(VK_END) & 0x8000)
                combo_pressed = pgdown_pressed and end_pressed

                if combo_pressed and not hotkey_latched:
                    hotkey_latched = True
                    callback()
                elif not combo_pressed:
                    hotkey_latched = False

                time.sleep(0.03)
        except Exception as error:
            self.last_error = str(error)
            startup_event.set()
        finally:
            self.hotkey_registered = False
            self.is_running = False
            self._startup_success = False

    def _run_pgdown_end_listener(self, callback, startup_event):
        if sys.platform.startswith("win"):
            self._run_windows_hotkey_listener(callback, startup_event)
            return

        try:
            from pynput import keyboard
        except Exception as error:
            self.last_error = f"pynput is unavailable: {error}"
            self.is_running = False
            startup_event.set()
            return

        try:
            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse("<page_down>+<end>"),
                callback,
            )

            listener = keyboard.Listener(
                on_press=lambda key: hotkey.press(listener.canonical(key)),
                on_release=lambda key: hotkey.release(listener.canonical(key)),
            )
            self._listener = listener
            listener.start()
            listener.wait()
            self.is_running = True
            self.hotkey_registered = True
            self._startup_success = True
            startup_event.set()
            listener.join()
        except Exception as error:
            self.last_error = str(error)
            startup_event.set()
        finally:
            self.hotkey_registered = False
            self.is_running = False
            self._startup_success = False
            self._listener = None

    def stop(self):
        self.is_running = False
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
