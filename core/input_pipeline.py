import threading
from concurrent.futures import ThreadPoolExecutor
from helpers.diagnostics import error_scope


class AsyncInputPipeline:
    """Moves command work off capture/UI threads while preserving command order."""

    def __init__(self, workers=2, capacity=6, on_error=None):
        self._executor = ThreadPoolExecutor(
            max_workers=1,  # Commands mutate shared state and must execute in submission order.
            thread_name_prefix="maya-input",
        )
        self._serial_gate = threading.Semaphore(1)
        self._slots = threading.BoundedSemaphore(max(1, int(capacity)))
        self._on_error = on_error
        self._pending = 0
        self._closed = False
        self._state_lock = threading.Lock()

    @property
    def is_busy(self):
        with self._state_lock:
            return self._pending > 0

    def submit(self, callback, *args, **kwargs):
        with self._state_lock:
            if self._closed or not self._slots.acquire(blocking=False):
                return False
            self._pending += 1
            try:
                future = self._executor.submit(self._run, callback, args, kwargs)
            except Exception:
                self._pending -= 1
                self._slots.release()
                raise
        future.add_done_callback(self._release_slot)
        return True

    def _release_slot(self, _future):
        with self._state_lock:
            self._pending -= 1
        self._slots.release()

    def _run(self, callback, args, kwargs):
        with error_scope():
            try:
                with self._serial_gate:
                    callback(*args, **kwargs)
            except Exception as error:
                if self._on_error:
                    self._on_error(error)

    def shutdown(self):
        with self._state_lock:
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
