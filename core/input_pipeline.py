import threading
from concurrent.futures import ThreadPoolExecutor


class AsyncInputPipeline:
    """Moves command work off capture/UI threads while preserving command order."""

    def __init__(self, workers=2, capacity=6, on_error=None):
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(workers)),
            thread_name_prefix="maya-input",
        )
        self._serial_gate = threading.Semaphore(1)
        self._slots = threading.BoundedSemaphore(max(1, int(capacity)))
        self._on_error = on_error
        self._closed = False
        self._state_lock = threading.Lock()

    def submit(self, callback, *args, **kwargs):
        with self._state_lock:
            if self._closed or not self._slots.acquire(blocking=False):
                return False
            try:
                self._executor.submit(self._run, callback, args, kwargs)
            except Exception:
                self._slots.release()
                raise
        return True

    def _run(self, callback, args, kwargs):
        try:
            with self._serial_gate:
                callback(*args, **kwargs)
        except Exception as error:
            if self._on_error:
                self._on_error(error)
        finally:
            self._slots.release()

    def shutdown(self):
        with self._state_lock:
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
