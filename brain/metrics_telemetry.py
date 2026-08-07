"""
ULTRON V3 - Unified Metrics Telemetry Exporter
Aggregates telemetry metrics across Task Engine, Message Router, Workspace Store, Agent Registry,
Health Monitor, Recovery Journal, and Garbage Collector for Mission Control.
Zero external framework dependencies.
"""

import os
import psutil
import threading
import time
from typing import Dict, Any, Optional

from core.interfaces import IService
from core.logger import logger


class MetricsTelemetry(IService):
    """
    Unified Metrics Telemetry Exporter.
    
    Purpose:
    - Collects and aggregates real-time telemetry metrics across all ULTRON V3 subsystems for Mission Control.
    
    Responsibilities:
    - Gathers system metrics (uptime, RAM, CPU, threads).
    - Collects subsystem telemetry metrics via dependency references.
    - Exports unified Mission Control JSON telemetry snapshots.
    
    Thread-Safety:
    - All metric collections and exports are guarded by an RLock.
    """

    def __init__(
        self,
        task_engine: Optional[Any] = None,
        message_router: Optional[Any] = None,
        workspace_store: Optional[Any] = None,
        agent_registry: Optional[Any] = None,
        health_monitor: Optional[Any] = None,
        recovery_journal: Optional[Any] = None,
        garbage_collector: Optional[Any] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.start_time = time.time()

        self.task_engine = task_engine
        self.message_router = message_router
        self.workspace_store = workspace_store
        self.agent_registry = agent_registry
        self.health_monitor = health_monitor
        self.recovery_journal = recovery_journal
        self.garbage_collector = garbage_collector

        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize metrics telemetry service."""
        with self._lock:
            if self._is_initialized:
                return
            self.start_time = time.time()
            self._is_initialized = True
            logger.info("[MetricsTelemetry] Unified Metrics Telemetry initialized.")

    def shutdown(self) -> None:
        """Cleanly shutdown telemetry service."""
        with self._lock:
            self._is_initialized = False
            logger.info("[MetricsTelemetry] Metrics Telemetry shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return metrics telemetry health status."""
        with self._lock:
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "uptime_seconds": round(time.time() - self.start_time, 2),
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration parameters."""
        pass

    def export_metrics(self) -> Dict[str, Any]:
        """
        Export unified metrics dictionary formatted for Mission Control.
        
        Returns:
            Dict[str, Any]: Mission Control telemetry snapshot.
        """
        with self._lock:
            now = time.time()
            uptime = round(now - self.start_time, 2)

            # System Process Metrics
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            ram_mb = round(mem_info.rss / (1024 * 1024), 2)
            threads_cnt = threading.active_count()
            cpu_percent = process.cpu_percent(interval=None)

            # Subsystem Metrics Extraction
            task_engine_metrics = {}
            if self.task_engine and hasattr(self.task_engine, "metrics"):
                task_engine_metrics = self.task_engine.metrics.to_dict()

            router_metrics = {}
            if self.message_router and hasattr(self.message_router, "get_router_metrics"):
                router_metrics = self.message_router.get_router_metrics()

            workspace_metrics = {}
            if self.workspace_store and hasattr(self.workspace_store, "health_check"):
                workspace_metrics = self.workspace_store.health_check()

            registry_metrics = {}
            if self.agent_registry and hasattr(self.agent_registry, "get_registry_metrics"):
                registry_metrics = self.agent_registry.get_registry_metrics()

            health_metrics = {}
            if self.health_monitor and hasattr(self.health_monitor, "get_health_snapshot"):
                health_metrics = self.health_monitor.get_health_snapshot()

            recovery_metrics = {}
            if self.recovery_journal and hasattr(self.recovery_journal, "get_replay_metrics"):
                recovery_metrics = self.recovery_journal.get_replay_metrics()

            gc_metrics = {}
            if self.garbage_collector and hasattr(self.garbage_collector, "get_gc_metrics"):
                gc_metrics = self.garbage_collector.get_gc_metrics()

            return {
                "system": {
                    "uptime_seconds": uptime,
                    "ram_usage_mb": ram_mb,
                    "thread_count": threads_cnt,
                    "cpu_percent": cpu_percent,
                },
                "task_engine": task_engine_metrics,
                "message_router": router_metrics,
                "workspace_store": workspace_metrics,
                "agent_registry": registry_metrics,
                "health_monitor": health_metrics,
                "recovery_journal": recovery_metrics,
                "garbage_collector": gc_metrics,
            }

    def get_snapshot(self) -> Dict[str, Any]:
        """Alias for export_metrics()."""
        return self.export_metrics()
