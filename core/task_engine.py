"""
ULTRON V3 - Priority Task Engine Framework
Multi-queue background execution scheduler, worker pool, lease manager, watchdog, and event bus integration.
Execution framework ONLY - zero routing or direct skill invocation logic.
"""

import math
import random
import threading
import time
import uuid
from queue import PriorityQueue, Empty
from typing import Dict, Any, List, Optional, Callable

from core.config import config
from core.event_bus import event_bus
from core.logger import logger
from core.task_metrics import TaskMetrics
from core.task_models import (
    TaskDescriptor,
    TaskResult,
    TaskStatus,
    PriorityLevel,
)


class TaskEngineSupervisor:
    """
    Supervisor component owning worker thread recovery.
    Subscribes to EventBus for WORKER_FAILED events and spawns replacement workers.
    """
    def __init__(self, task_engine: "TaskEngine") -> None:
        self.engine = task_engine
        self._subscribed = False

    def start(self) -> None:
        """Subscribe to Phase 1 EventBus worker recovery topic."""
        if not self._subscribed:
            event_bus.subscribe("WORKER_FAILED", self._handle_worker_failed)
            self._subscribed = True

    def _handle_worker_failed(self, **payload: Any) -> None:
        """Handle worker failure notification and spawn replacement worker."""
        worker_id = payload.get("worker_id", "unknown")
        reason = payload.get("reason", "unknown error")
        logger.warning(f"[Supervisor] Worker failure detected on '{worker_id}': {reason}. Spawning replacement worker...")
        self.engine._spawn_replacement_worker(worker_id)


class TaskEngine:
    """
    Priority Background Task Engine Framework.
    Manages queues, worker lifecycles, leases, retries, timeouts, and metrics.
    No singleton instance; instantiated by runtime container.
    """

    def __init__(
        self,
        worker_count: Optional[int] = None,
        queue_max_size: Optional[int] = None,
        max_retries: Optional[int] = None,
        lease_timeout: Optional[float] = None,
        watchdog_interval: Optional[float] = None,
        base_retry_delay: Optional[float] = None,
    ) -> None:
        # Read from core/config.py
        self.worker_count = worker_count or getattr(config, "TASK_ENGINE_WORKER_COUNT", 4)
        self.queue_max_size = queue_max_size or getattr(config, "TASK_ENGINE_QUEUE_MAX_SIZE", 1000)
        self.max_retries = max_retries or getattr(config, "TASK_ENGINE_MAX_RETRIES", 3)
        self.lease_timeout = lease_timeout or getattr(config, "TASK_ENGINE_LEASE_TIMEOUT", 30.0)
        self.watchdog_interval = watchdog_interval or getattr(config, "TASK_ENGINE_WATCHDOG_INTERVAL", 2.0)
        self.base_retry_delay = base_retry_delay or getattr(config, "TASK_ENGINE_BASE_RETRY_DELAY", 1.0)

        # Thread-safe storage
        self._lock = threading.RLock()
        self._priority_queue: PriorityQueue = PriorityQueue(maxsize=self.queue_max_size)
        self._tasks: Dict[str, TaskDescriptor] = {}
        self._dlq: List[TaskDescriptor] = []
        self._workers: Dict[str, threading.Thread] = {}
        self._worker_threads_active: Dict[str, bool] = {}
        
        # State control flags
        self._is_paused = False
        self._is_running = False
        self._stop_event = threading.Event()

        # Telemetry Metrics
        self.metrics = TaskMetrics(worker_count=self.worker_count)

        # Watchdog Thread & Supervisor
        self._watchdog_thread: Optional[threading.Thread] = None
        self.supervisor = TaskEngineSupervisor(self)

    def start(self) -> None:
        """Start the Task Engine worker threads, supervisor, and watchdog."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()

            # Start supervisor
            self.supervisor.start()

            # Spawn workers
            for i in range(self.worker_count):
                worker_id = f"worker_{i + 1}"
                self._spawn_worker(worker_id)

            # Start Watchdog thread
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                name="TaskEngineWatchdog",
                daemon=True,
            )
            self._watchdog_thread.start()
            logger.info(f"[TaskEngine] Started with {self.worker_count} workers and Watchdog.")

    def _spawn_worker(self, worker_id: str) -> None:
        """Spawn a daemon worker thread."""
        with self._lock:
            self._worker_threads_active[worker_id] = True
            t = threading.Thread(
                target=self._worker_loop,
                args=(worker_id,),
                name=f"TaskEngineWorker-{worker_id}",
                daemon=True,
            )
            self._workers[worker_id] = t
            t.start()
            event_bus.publish("WORKER_STARTED", worker_id=worker_id)

    def _spawn_replacement_worker(self, failed_worker_id: str) -> None:
        """Called by Supervisor to replace a dead worker thread."""
        with self._lock:
            if not self._is_running:
                return
            new_worker_id = f"{failed_worker_id}_repl_{uuid.uuid4().hex[:4]}"
            self._spawn_worker(new_worker_id)

    def validate_task(self, task: TaskDescriptor) -> bool:
        """Validate task schema and update status CREATED -> VALIDATED."""
        if not task.task_id or not isinstance(task.priority, PriorityLevel):
            return False
        task.status = TaskStatus.VALIDATED
        return True

    def enqueue(self, task: TaskDescriptor) -> bool:
        """
        Enqueue a task for execution.
        Follows lifecycle: CREATED -> VALIDATED -> QUEUED.
        """
        with self._lock:
            if not self.validate_task(task):
                task.status = TaskStatus.FAILED
                return False

            task.status = TaskStatus.QUEUED
            self._tasks[task.task_id] = task

            try:
                self._priority_queue.put(task, block=False)
                self.metrics.record_enqueue()
                self._update_pending_age_metric()
                return True
            except Exception as e:
                logger.error(f"[TaskEngine] Failed to enqueue task {task.task_id}: {e}")
                task.status = TaskStatus.FAILED
                return False

    def pause(self) -> None:
        """Pause worker processing of queued tasks."""
        with self._lock:
            self._is_paused = True
            logger.info("[TaskEngine] Queue processing paused.")

    def resume(self) -> None:
        """Resume worker processing of queued tasks."""
        with self._lock:
            self._is_paused = False
            logger.info("[TaskEngine] Queue processing resumed.")

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task by task_id."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.DLQ]:
                return False

            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            if task.lease_token:
                task.lease_token = None
                task.lease_owner = None

            logger.info(f"[TaskEngine] Task '{task_id}' set to CANCELLED.")
            return True

    def get_task(self, task_id: str) -> Optional[TaskDescriptor]:
        """Retrieve task descriptor by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def get_dlq(self) -> List[TaskDescriptor]:
        """Get copies of all tasks in the Dead Letter Queue."""
        with self._lock:
            return list(self._dlq)

    def _worker_loop(self, worker_id: str) -> None:
        """Worker thread processing loop."""
        while not self._stop_event.is_set():
            if self._is_paused:
                time.sleep(0.1)
                continue

            try:
                task: TaskDescriptor = self._priority_queue.get(timeout=0.1)
            except Empty:
                continue

            with self._lock:
                # Skip cancelled or already processed tasks
                if task.status == TaskStatus.CANCELLED:
                    self._priority_queue.task_done()
                    continue

                # DISPATCHED -> RUNNING
                task.status = TaskStatus.DISPATCHED
                lease_token = f"lease_{uuid.uuid4().hex[:8]}"
                now = time.time()
                task.lease_owner = worker_id
                task.lease_token = lease_token
                task.lease_expiry = now + (task.timeout or self.lease_timeout)
                task.started_at = now
                task.heartbeat_at = now
                task.status = TaskStatus.RUNNING
                self.metrics.active_tasks += 1

            wait_ms = (task.started_at - task.created_at) * 1000.0
            event_bus.publish("TASK_STARTED", task_id=task.task_id, worker_id=worker_id)

            start_exec = time.time()
            success = False
            err_msg = None

            try:
                if task.exec_func and callable(task.exec_func):
                    task.exec_func()
                success = True
            except Exception as ex:
                success = False
                err_msg = str(ex)
                logger.error(f"[TaskEngine] Worker {worker_id} exception on task {task.task_id}: {ex}")

            exec_ms = (time.time() - start_exec) * 1000.0

            with self._lock:
                if task.status == TaskStatus.CANCELLED:
                    self.metrics.active_tasks = max(0, self.metrics.active_tasks - 1)
                    self._priority_queue.task_done()
                    continue

                if success:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
                    task.lease_token = None
                    task.lease_owner = None
                    self.metrics.record_completion(exec_ms, wait_ms, task.retry_count)
                    event_bus.publish("TASK_FINISHED", task_id=task.task_id, worker_id=worker_id)
                else:
                    self._handle_task_failure(task, err_msg)

                self._priority_queue.task_done()

    def _handle_task_failure(self, task: TaskDescriptor, error_msg: Optional[str]) -> None:
        """Handle task execution failure with retry or DLQ routing."""
        task.retry_count += 1
        if task.retry_count < task.max_retries:
            task.status = TaskStatus.QUEUED
            task.lease_token = None
            task.lease_owner = None

            # Calculate exponential backoff wait
            backoff_sec = self.base_retry_delay * (2 ** (task.retry_count - 1)) + random.uniform(0.0, 0.2)
            event_bus.publish("TASK_RETRY", task_id=task.task_id, retry_count=task.retry_count, backoff=backoff_sec)

            # Re-enqueue in background thread after backoff delay
            def delayed_requeue():
                time.sleep(backoff_sec)
                with self._lock:
                    if task.status != TaskStatus.CANCELLED:
                        try:
                            self._priority_queue.put(task, block=False)
                        except Exception:
                            pass

            threading.Thread(target=delayed_requeue, daemon=True).start()
            self.metrics.record_failure(is_dlq=False)
        else:
            task.status = TaskStatus.DLQ
            task.completed_at = time.time()
            task.lease_token = None
            task.lease_owner = None
            self._dlq.append(task)
            self.metrics.record_failure(is_dlq=True)
            event_bus.publish("TASK_FAILED", task_id=task.task_id, error=error_msg, dlq=True)

    def _watchdog_loop(self) -> None:
        """
        Watchdog monitoring thread.
        Monitors health, detects expired leases & timed-out tasks, and publishes WORKER_FAILED events.
        Does NOT restart workers directly (Supervisor handles WORKER_FAILED events).
        """
        while not self._stop_event.is_set():
            time.sleep(self.watchdog_interval)
            now = time.time()

            with self._lock:
                if not self._is_running:
                    break

                # 1. Check for expired task leases and timeouts
                for task_id, task in list(self._tasks.items()):
                    if task.status == TaskStatus.RUNNING:
                        if task.lease_expiry and now > task.lease_expiry:
                            logger.warning(f"[Watchdog] Task {task_id} timed out (lease expired).")
                            task.status = TaskStatus.CANCELLED
                            event_bus.publish("TASK_TIMEOUT", task_id=task_id, owner=task.lease_owner)

                # 2. Check for dead worker threads
                for worker_id, thread in list(self._workers.items()):
                    if not thread.is_alive() and self._worker_threads_active.get(worker_id, False):
                        logger.error(f"[Watchdog] Detected dead worker thread '{worker_id}'. Publishing WORKER_FAILED event...")
                        self._worker_threads_active[worker_id] = False
                        event_bus.publish("WORKER_FAILED", worker_id=worker_id, reason="Thread non-responsive or crashed")

                # 3. Update oldest pending task age metric
                self._update_pending_age_metric()

    def _update_pending_age_metric(self) -> None:
        """Calculate age of oldest pending task."""
        now = time.time()
        oldest_age = 0.0
        for task in self._tasks.values():
            if task.status in [TaskStatus.QUEUED, TaskStatus.DISPATCHED]:
                age = now - task.created_at
                if age > oldest_age:
                    oldest_age = age
        self.metrics.oldest_pending_task_age = round(oldest_age, 2)

    def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully shutdown worker threads and watchdog."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            self._stop_event.set()

        # Wait for worker threads to complete
        start_wait = time.time()
        for t in list(self._workers.values()):
            rem_time = max(0.1, timeout - (time.time() - start_wait))
            t.join(timeout=rem_time)

        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=1.0)

        logger.info("[TaskEngine] Shutdown complete.")
