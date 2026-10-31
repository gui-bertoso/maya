"""One capture engine at a time: Whisper primary, lazy Vosk fallback.

A failed utterance is discarded rather than replayed as a delayed command.
Fallback lasts until stop/restart or settings reapplication; no retry loop.
"""
import threading
from input.voice import Voice


class GuardedVoskVoice(Voice):
    def __init__(self, can_capture, **kwargs):
        super().__init__(**kwargs)
        self.can_capture = can_capture

    def audio_callback(self, indata, frames, time, status):
        if self.can_capture():
            super().audio_callback(indata, frames, time, status)


class FailoverVoice:
    def __init__(self, primary, fallback_factory, on_engine_change=None):
        self.primary = primary
        self.fallback_factory = fallback_factory
        self.on_engine_change = on_engine_change
        self.active = primary
        self.active_engine = 'whisper.cpp'
        self.status = 'idle'
        self.last_error = None
        self.thread = None
        self._lock = threading.RLock()
        self._stopped = threading.Event()
        self._generation = 0

    @property
    def is_listening(self):
        return bool(self.active and self.active.is_listening)

    @property
    def is_loaded(self):
        return bool(self.active and self.active.is_loaded)

    def _valid(self, generation, engine):
        return not self._stopped.is_set() and generation == self._generation and engine is self.active

    def start_background(self, on_final_text=None, on_partial_text=None, on_status_change=None):
        with self._lock:
            if self.thread and self.thread.is_alive():
                return not self._stopped.is_set()
            self._generation += 1
            generation = self._generation
            self._stopped.clear()
            self.active = self.primary
            self.active_engine = 'whisper.cpp'
            self.status = 'loading'
            self.last_error = None
            if on_status_change:
                on_status_change('loading')
            self.thread = threading.Thread(target=self._run,
                args=(generation, on_final_text, on_partial_text, on_status_change),
                daemon=True, name='maya-stt-failover')
            self.thread.start()
            return True

    @staticmethod
    def _stop_engine(engine):
        try:
            engine.stop()
        except Exception:
            return False
        thread = getattr(engine, 'thread', None)
        if thread and thread is not threading.current_thread():
            thread.join(timeout=3)
            return not thread.is_alive()
        return True

    def _run(self, generation, on_final_text, on_partial_text, on_status_change):
        for stage in ('whisper.cpp', 'vosk'):
            if self._stopped.is_set() or generation != self._generation:
                return
            if stage == 'vosk':
                try:
                    backup = self.fallback_factory()
                except Exception as error:
                    self.last_error = type(error).__name__
                    break
                with self._lock:
                    if self._stopped.is_set() or generation != self._generation:
                        return
                    self.active = backup
                    self.active_engine = stage
                if getattr(self.primary, 'DEBUG_MODE', False):
                    print('[stt] whisper.cpp unavailable; switching to vosk', flush=True)
                if self.on_engine_change:
                    self.on_engine_change(stage)
            engine = self.active
            failed = threading.Event()

            def status(value, engine=engine, failed=failed):
                if not self._valid(generation, engine):
                    return
                if value in {'error', 'unavailable'}:
                    self.last_error = getattr(engine, 'last_error', None)
                    failed.set()
                    # Keep the app from restarting the failed engine while switching.
                    value = 'loading'
                self.status = value
                if on_status_change:
                    on_status_change(value)

            def final(text, engine=engine, failed=failed):
                if self._valid(generation, engine) and not failed.is_set() and on_final_text:
                    on_final_text(text)

            def partial(text, engine=engine, failed=failed):
                if self._valid(generation, engine) and not failed.is_set() and on_partial_text:
                    on_partial_text(text)

            try:
                started = engine.start_background(final, partial, status)
                if not started:
                    failed.set()
                while not self._stopped.is_set() and generation == self._generation:
                    if failed.wait(.1):
                        break
                    worker = getattr(engine, 'thread', None)
                    if worker and not worker.is_alive():
                        failed.set()
                        break
            except Exception as error:
                self.last_error = type(error).__name__
                failed.set()
            # Invalidate callbacks before stop emits idle or a late result.
            with self._lock:
                if generation == self._generation:
                    self.active = None
            stopped_cleanly = self._stop_engine(engine)
            if self._stopped.is_set() or generation != self._generation:
                return
            if not stopped_cleanly:
                self.last_error = 'Capture worker did not stop; refusing overlapping capture'
                break
        if not self._stopped.is_set() and generation == self._generation:
            self.status = 'error'
            if on_status_change:
                on_status_change('error')

    def stop(self):
        with self._lock:
            self._stopped.set()
            self._generation += 1
            active = self.active
            self.active = None
        if active is not None:
            self._stop_engine(active)
        supervisor = self.thread
        if supervisor and supervisor is not threading.current_thread():
            supervisor.join(timeout=1)
        self.status = 'idle'
