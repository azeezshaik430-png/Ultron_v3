"""
ULTRON V3 - Task Metrics
Dedicated metrics module for runtime task engine telemetry.
Zero external framework dependencies.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class TaskMetrics:
    """Task Engine runtime telemetry metrics container."""
    throughput_per_sec: float = 0.0
    active_tasks: int = 0
    queued_tasks: int = 0
    waiting_tasks: int = 0
    retry_count: int = 0
    dlq_size: int = 0
    worker_count: int = 0
    execution_latency_ms: float = 0.0
    success_rate: float = 100.0
    failure_rate: float = 0.0
    average_retry_count: float = 0.0
    average_queue_wait_ms: float = 0.0
    worker_utilization: float = 0.0
    oldest_pending_task_age: float = 0.0
    
    # Internal Counters
    total_completed: int = 0
    total_failed: int = 0
    total_enqueued: int = 0
    total_latency_ms_sum: float = 0.0
    total_wait_ms_sum: float = 0.0
    total_retry_sum: int = 0
    start_time: float = field(default_factory=time.time)

    def record_enqueue(self) -> None:
        """Record task enqueued metric."""
        self.total_enqueued += 1
        self.queued_tasks += 1

    def record_completion(self, execution_ms: float, wait_ms: float, retries: int) -> None:
        """Record task completion telemetry."""
        self.total_completed += 1
        if self.queued_tasks > 0:
            self.queued_tasks -= 1
        if self.active_tasks > 0:
            self.active_tasks -= 1

        self.total_latency_ms_sum += execution_ms
        self.total_wait_ms_sum += wait_ms
        self.total_retry_sum += retries

        self._update_averages()

    def record_failure(self, is_dlq: bool = False) -> None:
        """Record task failure telemetry."""
        self.total_failed += 1
        self.retry_count += 1
        if is_dlq:
            self.dlq_size += 1
        if self.active_tasks > 0:
            self.active_tasks -= 1

        self._update_averages()

    def _update_averages(self) -> None:
        """Recalculate throughput, success/failure rates, and averages."""
        elapsed = max(0.001, time.time() - self.start_time)
        self.throughput_per_sec = round(self.total_completed / elapsed, 2)

        total_finished = self.total_completed + self.total_failed
        if total_finished > 0:
            self.success_rate = round((self.total_completed / total_finished) * 100.0, 2)
            self.failure_rate = round((self.total_failed / total_finished) * 100.0, 2)
            self.execution_latency_ms = round(self.total_latency_ms_sum / total_finished, 2)
            self.average_queue_wait_ms = round(self.total_wait_ms_sum / total_finished, 2)
            self.average_retry_count = round(self.total_retry_sum / total_finished, 2)

        if self.worker_count > 0:
            self.worker_utilization = round(min(100.0, (self.active_tasks / self.worker_count) * 100.0), 2)

    def to_dict(self) -> Dict[str, Any]:
        """Export telemetry dictionary for Mission Control dashboard."""
        self._update_averages()
        return {
            "throughput_per_sec": self.throughput_per_sec,
            "active_tasks": self.active_tasks,
            "queued_tasks": self.queued_tasks,
            "waiting_tasks": self.waiting_tasks,
            "retry_count": self.retry_count,
            "dlq_size": self.dlq_size,
            "worker_count": self.worker_count,
            "execution_latency_ms": self.execution_latency_ms,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "average_retry_count": self.average_retry_count,
            "average_queue_wait_ms": self.average_queue_wait_ms,
            "worker_utilization": self.worker_utilization,
            "oldest_pending_task_age": self.oldest_pending_task_age,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_enqueued": self.total_enqueued,
        }
