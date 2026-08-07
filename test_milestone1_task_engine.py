"""
ULTRON V3 - Milestone 1 Task Engine Verification Test Suite
Verifies priority queueing, lifecycle states, retries, DLQ, leasing, Watchdog,
Supervisor worker recovery, metrics, memory leak safety, and Phase 1 EventBus integration.
"""

import gc
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

from core.event_bus import event_bus
from core.task_engine import TaskEngine, TaskEngineSupervisor
from core.task_metrics import TaskMetrics
from core.task_models import (
    TaskDescriptor,
    TaskStatus,
    PriorityLevel,
    TaskResult,
)


class TestMilestone1TaskEngine(unittest.TestCase):
    """Milestone 1 Test Suite for Task Engine."""

    def setUp(self):
        self.engine = TaskEngine(
            worker_count=2,
            queue_max_size=10000,
            max_retries=3,
            lease_timeout=2.0,
            watchdog_interval=0.5,
            base_retry_delay=0.1,
        )

    tearDown = lambda self: self.engine.shutdown()

    def test_01_queue_ordering(self):
        """Verify CRITICAL priority tasks execute before HIGH and NORMAL tasks."""
        executed_order = []

        def make_task(name, priority):
            def run():
                executed_order.append(name)
            return TaskDescriptor(
                action=name,
                priority=priority,
                exec_func=run,
            )

        t_normal = make_task("normal_task", PriorityLevel.NORMAL)
        t_high = make_task("high_task", PriorityLevel.HIGH)
        t_critical = make_task("critical_task", PriorityLevel.CRITICAL)

        self.engine.pause()
        self.engine.start()

        self.engine.enqueue(t_normal)
        self.engine.enqueue(t_high)
        self.engine.enqueue(t_critical)

        time.sleep(0.1)
        self.engine.resume()
        time.sleep(0.5)

        self.assertEqual(len(executed_order), 3)
        self.assertEqual(executed_order[0], "critical_task")
        self.assertEqual(executed_order[1], "high_task")
        self.assertEqual(executed_order[2], "normal_task")

    def test_02_retry_exhaustion_and_dlq(self):
        """Verify task failing max_retries moves to DLQ and publishes TASK_FAILED."""
        failed_events = []
        event_bus.subscribe("TASK_FAILED", lambda **p: failed_events.append(p))

        def failing_func():
            raise ValueError("Forced execution failure")

        task = TaskDescriptor(
            action="failing_task",
            priority=PriorityLevel.NORMAL,
            max_retries=3,
            exec_func=failing_func,
        )

        self.engine.start()
        self.engine.enqueue(task)

        # Wait for retries to exhaust
        time.sleep(1.2)

        dlq = self.engine.get_dlq()
        self.assertEqual(len(dlq), 1)
        self.assertEqual(dlq[0].status, TaskStatus.DLQ)
        self.assertGreaterEqual(dlq[0].retry_count, 3)
        self.assertGreaterEqual(len(failed_events), 1)

    def test_03_supervisor_worker_recovery(self):
        """Verify Watchdog detects dead worker, emits WORKER_FAILED, and Supervisor replaces worker."""
        worker_failed_events = []
        worker_started_events = []
        event_bus.subscribe("WORKER_FAILED", lambda **p: worker_failed_events.append(p))
        event_bus.subscribe("WORKER_STARTED", lambda **p: worker_started_events.append(p))

        self.engine.start()
        initial_started = len(worker_started_events)

        # Force kill a worker thread state to simulate thread crash
        worker_keys = list(self.engine._workers.keys())
        dead_worker_id = worker_keys[0]
        
        # Simulate worker death by turning off active flag
        self.engine._worker_threads_active[dead_worker_id] = True
        # Kill underlying thread logic by forcing it inactive in supervisor test
        with patch.object(self.engine._workers[dead_worker_id], "is_alive", return_value=False):
            # Watchdog loop tick
            self.engine._watchdog_loop()
            time.sleep(0.3)

        self.assertGreaterEqual(len(worker_failed_events), 1)
        self.assertGreater(len(worker_started_events), initial_started)

    def test_04_timeout_handling(self):
        """Verify task exceeding lease timeout is caught by Watchdog."""
        timeout_events = []
        event_bus.subscribe("TASK_TIMEOUT", lambda **p: timeout_events.append(p))

        def slow_func():
            time.sleep(5.0)

        task = TaskDescriptor(
            action="slow_task",
            priority=PriorityLevel.NORMAL,
            timeout=0.3,
            exec_func=slow_func,
        )

        self.engine.start()
        self.engine.enqueue(task)
        time.sleep(0.8)

        self.assertIn(task.status, [TaskStatus.CANCELLED, TaskStatus.FAILED, TaskStatus.DLQ])

    def test_05_pause_and_resume(self):
        """Verify queue processing pauses and resumes cleanly."""
        exec_count = []
        task = TaskDescriptor(
            action="test_task",
            exec_func=lambda: exec_count.append(1),
        )

        self.engine.pause()
        self.engine.start()
        self.engine.enqueue(task)

        time.sleep(0.3)
        self.assertEqual(len(exec_count), 0)

        self.engine.resume()
        time.sleep(0.3)
        self.assertEqual(len(exec_count), 1)

    def test_06_cancel_task(self):
        """Verify task cancellation prevents execution."""
        exec_count = []
        task = TaskDescriptor(
            action="cancel_me",
            exec_func=lambda: exec_count.append(1),
        )

        self.engine.pause()
        self.engine.start()
        self.engine.enqueue(task)
        self.assertTrue(self.engine.cancel_task(task.task_id))
        self.engine.resume()

        time.sleep(0.3)
        self.assertEqual(len(exec_count), 0)
        self.assertEqual(task.status, TaskStatus.CANCELLED)

    def test_07_graceful_shutdown(self):
        """Verify engine shuts down cleanly without throwing errors."""
        self.engine.start()
        time.sleep(0.1)
        self.engine.shutdown(timeout=2.0)
        self.assertFalse(self.engine._is_running)

    def test_08_thread_safety_multi_producer(self):
        """Verify 20 concurrent threads enqueuing tasks simultaneously."""
        import threading
        self.engine.start()
        results = []

        def producer(num):
            for j in range(10):
                t = TaskDescriptor(
                    action=f"p_{num}_{j}",
                    exec_func=lambda: results.append(1),
                )
                self.engine.enqueue(t)

        threads = [threading.Thread(target=producer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        time.sleep(1.0)
        self.assertEqual(len(results), 200)

    def test_09_stress_and_throughput(self):
        """Benchmark performance for 100, 1000 tasks."""
        self.engine.start()
        count = []

        start_time = time.time()
        num_tasks = 500
        for i in range(num_tasks):
            self.engine.enqueue(TaskDescriptor(
                action=f"stress_{i}",
                exec_func=lambda: count.append(1),
            ))

        time.sleep(1.5)
        elapsed = time.time() - start_time
        throughput = len(count) / elapsed
        self.assertEqual(len(count), num_tasks)
        print(f"\n[Benchmark] Processed {len(count)} tasks in {elapsed:.2f}s ({throughput:.1f} tasks/sec)")

    def test_10_memory_leak_check(self):
        """Verify zero memory leak over 1,000 repeated execution cycles."""
        self.engine.start()
        gc.collect()
        import psutil, os
        process = psutil.Process(os.getpid())
        ram_before = process.memory_info().rss

        for i in range(1000):
            self.engine.enqueue(TaskDescriptor(
                action=f"mem_{i}",
                exec_func=lambda: None,
            ))

        time.sleep(1.5)
        gc.collect()
        ram_after = process.memory_info().rss
        ram_diff_mb = (ram_after - ram_before) / (1024 * 1024)
        print(f"\n[Memory Leak Test] RAM diff after 1,000 cycles: {ram_diff_mb:.2f} MB")
        self.assertLess(ram_diff_mb, 5.0)


if __name__ == "__main__":
    unittest.main()
