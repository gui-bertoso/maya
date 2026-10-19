import os
import sys


def _is_enabled(value):
    return str(value or "").strip().lower() == "true"


def should_enable_runtime_console(env_getter=None):
    getter = env_getter or os.getenv
    return _is_enabled(getter("DEBUG_MODE", "false")) and _is_enabled(
        getter("MAYA_ENABLE_RUNTIME_CONSOLE", "false")
    )


class RuntimeConsole:
    def __init__(self):
        self._attached = False
        self._stdin = None
        self._stdout = None
        self._stderr = None
        self._previous_stdin = None
        self._previous_stdout = None
        self._previous_stderr = None

    def sync(self, enabled):
        if enabled:
            self.attach()
        else:
            self.detach()

    def attach(self):
        if self._attached or not sys.platform.startswith("win") or not getattr(sys, "frozen", False):
            return False

        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            attached = bool(kernel32.AttachConsole(-1))
            if not attached:
                attached = bool(kernel32.AllocConsole())
            if not attached:
                return False

            self._previous_stdin = sys.stdin
            self._previous_stdout = sys.stdout
            self._previous_stderr = sys.stderr

            self._stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
            self._stdout = open("CONOUT$", "w", buffering=1, encoding="utf-8", errors="replace")
            self._stderr = open("CONOUT$", "w", buffering=1, encoding="utf-8", errors="replace")
            sys.stdin = self._stdin
            sys.stdout = self._stdout
            sys.stderr = self._stderr
            self._attached = True
            return True
        except Exception:
            return False

    def detach(self):
        if not self._attached or not sys.platform.startswith("win") or not getattr(sys, "frozen", False):
            return False

        try:
            import ctypes

            sys.stdin = self._previous_stdin or sys.__stdin__
            sys.stdout = self._previous_stdout or sys.__stdout__
            sys.stderr = self._previous_stderr or sys.__stderr__

            for stream_name in ("_stdin", "_stdout", "_stderr"):
                stream = getattr(self, stream_name)
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
                    setattr(self, stream_name, None)

            ctypes.windll.kernel32.FreeConsole()
            self._attached = False
            return True
        except Exception:
            return False
