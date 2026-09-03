import threading
import time
import unittest

from core.input_pipeline import AsyncInputPipeline


class AsyncInputPipelineTests(unittest.TestCase):
    def test_submit_is_non_blocking_and_work_runs_elsewhere(self):
        completed = threading.Event()
        caller_thread = threading.get_ident()
        worker_threads = []
        pipeline = AsyncInputPipeline()

        started = time.perf_counter()
        accepted = pipeline.submit(lambda: (worker_threads.append(threading.get_ident()), completed.set()))
        elapsed = time.perf_counter() - started

        self.assertTrue(accepted)
        self.assertLess(elapsed, 0.1)
        self.assertTrue(completed.wait(1.0))
        self.assertNotEqual(worker_threads[0], caller_thread)
        pipeline.shutdown()

    def test_semaphore_prevents_overlapping_command_processing(self):
        pipeline = AsyncInputPipeline(workers=3, capacity=3)
        lock = threading.Lock()
        finished = threading.Event()
        active = 0
        maximum_active = 0
        completed = 0

        def work():
            nonlocal active, maximum_active, completed
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.02)
            with lock:
                active -= 1
                completed += 1
                if completed == 3:
                    finished.set()

        for _ in range(3):
            self.assertTrue(pipeline.submit(work))

        self.assertTrue(finished.wait(1.0))
        self.assertEqual(maximum_active, 1)
        pipeline.shutdown()

    def test_capacity_applies_backpressure(self):
        release = threading.Event()
        pipeline = AsyncInputPipeline(workers=1, capacity=1)
        self.assertTrue(pipeline.submit(release.wait, 1.0))
        self.assertFalse(pipeline.submit(lambda: None))
        release.set()
        pipeline.shutdown()


if __name__ == "__main__":
    unittest.main()
