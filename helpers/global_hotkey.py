from helpers.diagnostics import report_error
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

    def start_delete_pgup(self, callback):
        if self.thread and self.thread.is_alive():
            return True

        self.last_error = None
        self._startup_success = False
        startup_event = threading.Event()
        self.thread = threading.Thread(
            target=self._run_delete_pgup_listener,
            args=(callback, startup_event),
            daemon=True,
        )
        self.thread.start()
        startup_event.wait(2.0)
        return self._startup_success

    def _run_windows_hotkey_listener(self, callback, startup_event):
        # Prefer pynput's low-level Windows hook. It receives the actual
        # keyboard events even when Maya is not the foreground window.
        try:
            from pynput import keyboard

            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse("<delete>+<page_up>"),
                callback,
            )

            listener = keyboard.Listener(
                on_press=lambda key: hotkey.press(listener.canonical(key)),
                on_release=lambda key: hotkey.release(listener.canonical(key)),
            )
            self._listener = listener
            listener.start()
            if not listener.is_alive():
                raise RuntimeError("keyboard listener stopped during startup")

            self.is_running = True
            self.hotkey_registered = True
            self._startup_success = True
            startup_event.set()
            listener.join()
            return
        except Exception as error:
            report_error("hotkey", error, operation="global_hotkey._run_windows_hotkey_listener", notify=False)
            self.last_error = f"pynput hotkey unavailable: {error}"
            self._listener = None

        # Keep the polling implementation as a fallback for environments
        # where pynput cannot install its Windows hook.
        try:
            import ctypes

            user32 = ctypes.windll.user32
            VK_PRIOR = 0x21
            VK_DELETE = 0x2E
            hotkey_latched = False

            self.is_running = True
            self.hotkey_registered = True
            self._startup_success = True
            startup_event.set()

            while self.is_running:
                pgup_pressed = bool(user32.GetAsyncKeyState(VK_PRIOR) & 0x8000)
                delete_pressed = bool(user32.GetAsyncKeyState(VK_DELETE) & 0x8000)
                combo_pressed = pgup_pressed and delete_pressed

                if combo_pressed and not hotkey_latched:
                    hotkey_latched = True
                    callback()
                elif not combo_pressed:
                    hotkey_latched = False

                time.sleep(0.03)
        except Exception as error:
            report_error("hotkey", error, operation="global_hotkey._run_windows_hotkey_listener", notify=False)
            self.last_error = str(error)
            startup_event.set()
        finally:
            self.hotkey_registered = False
            self.is_running = False
            self._startup_success = False

    def _run_delete_pgup_listener(self, callback, startup_event):
        if sys.platform.startswith("win"):
            self._run_windows_hotkey_listener(callback, startup_event)
            return

        try:
            from pynput import keyboard
        except Exception as error:
            report_error("hotkey", error, operation="global_hotkey._run_delete_pgup_listener", notify=False)
            self.last_error = f"pynput is unavailable: {error}"
            self.is_running = False
            startup_event.set()
            return

        try:
            # Open the input only after both keys are released. Otherwise the
            # new window can receive the tail of the shortcut (or auto-repeat).
            combo = set(keyboard.HotKey.parse("<delete>+<page_up>"))
            pressed = set()
            pending = False

            def on_press(key):
                nonlocal pending
                pressed.add(listener.canonical(key))
                if combo.issubset(pressed):
                    pending = True

            def on_release(key):
                nonlocal pending
                pressed.discard(listener.canonical(key))
                if pending and not combo.intersection(pressed):
                    pending = False
                    callback()

            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._listener = listener
            listener.start()
            listener.wait()
            self.is_running = True
            self.hotkey_registered = True
            self._startup_success = True
            startup_event.set()
            listener.join()
        except Exception as error:
            report_error("hotkey", error, operation="global_hotkey._run_delete_pgup_listener", notify=False)
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
