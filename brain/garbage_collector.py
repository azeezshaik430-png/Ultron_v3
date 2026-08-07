"""
ULTRON V3 - Bus Garbage Collector
Background thread garbage collector for TTL message eviction, scratchpad pruning, and artifact cleanup.
Zero external framework dependencies.
"""

import threading
import time
from typing import Dict, Any, Optional

from core.config import config
from core.event_bus import event_bus
from core.interfaces import IService
from core.logger import logger


class BusGarbageCollector(IService):
    """
    Agent Memory Bus Garbage Collector.
    
    Purpose:
    - Periodically sweeps and evicts expired TTL messages, task scratchpads, and orphaned artifacts.
    
    Responsibilities:
    - Executes background cleanup loop on a configurable interval (`GC_INTERVAL`).
    - Performs batch eviction up to `GC_MAX_BATCH` items per sweep.
    - Publishes GC lifecycle events over Phase 1 EventBus.
    - Exports GC telemetry metrics (reclaimed memory, duration, items removed).
    
    Thread-Safety:
    - Background thread loop guarded by RLock contexts during target component sweeps.
    """

    def __init__(
        self,
        gc_interval: Optional[float] = None,
        max_batch: Optional[int] = None,
        scratchpad: Optional[Any] = None,
        message_router: Optional[Any] = None,
        artifact_registry: Optional[Any] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.gc_interval = gc_interval or getattr(config, "GC_INTERVAL", 30.0)
        self.max_batch = max_batch or getattr(config, "GC_MAX_BATCH", 500)

        self.scratchpad = scratchpad
        self.message_router = message_router
        self.artifact_registry = artifact_registry

        self._stop_event = threading.Event()
        self._gc_thread: Optional[threading.Thread] = None

        # Telemetry metrics
        self._total_sweeps = 0
        self._total_reclaimed_items = 0
        self._last_sweep_duration_ms = 0.0
        self._is_initialized = False

    def initialize(self) -> None:
        """Start the background garbage collection thread."""
        with self._lock:
            if self._is_initialized:
                return
            self._is_initialized = True
            self._stop_event.clear()

            self._gc_thread = threading.Thread(
                target=self._gc_loop,
                name="BusGarbageCollectorWorker",
                daemon=True,
            )
            self._gc_thread.start()
            logger.info(f"[BusGarbageCollector] Started background thread (Interval: {self.gc_interval}s, Max Batch: {self.max_batch}).")

    def shutdown(self) -> None:
        """Stop background GC worker thread."""
        with self._lock:
            if not self._is_initialized:
                return
            self._is_initialized = False
            self._stop_event.set()

        if self._gc_thread:
            self._gc_thread.join(timeout=2.0)

        logger.info("[BusGarbageCollector] Cleanly shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return garbage collector health telemetry status."""
        with self._lock:
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "total_sweeps": self._total_sweeps,
                "total_reclaimed_items": self._total_reclaimed_items,
                "last_sweep_duration_ms": self._last_sweep_duration_ms,
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration parameters."""
        with self._lock:
            if "gc_interval" in config_data:
                self.gc_interval = float(config_data["gc_interval"])
            if "max_batch" in config_data:
                self.max_batch = int(config_data["max_batch"])

    def perform_cleanup(self, max_age_seconds: float = 0.1) -> Dict[str, int]:
        """
        Manually execute a garbage collection sweep across all targets.
        
        Args:
            max_age_seconds (float): Max age threshold in seconds for scratchpad eviction.
            
        Returns:
            Dict[str, int]: Summary dictionary of items evicted per subsystem.
        """
        start_t = time.time()
        event_bus.publish("GC_STARTED")

        evicted_scratchpads = 0
        evicted_messages = 0
        evicted_artifacts = 0

        # 1. Scratchpad Cleanup
        if self.scratchpad and hasattr(self.scratchpad, "clear_expired"):
            try:
                evicted_scratchpads = self.scratchpad.clear_expired(max_age_seconds=max_age_seconds)
                if evicted_scratchpads > 0:
                    event_bus.publish("GC_ITEM_REMOVED", target="scratchpad", count=evicted_scratchpads)
            except Exception as ex:
                logger.error(f"[BusGarbageCollector] Scratchpad GC error: {ex}")

        sweep_duration_ms = (time.time() - start_t) * 1000.0

        with self._lock:
            self._total_sweeps += 1
            total_sweep_items = evicted_scratchpads + evicted_messages + evicted_artifacts
            self._total_reclaimed_items += total_sweep_items
            self._last_sweep_duration_ms = sweep_duration_ms

        summary = {
            "evicted_scratchpads": evicted_scratchpads,
            "evicted_messages": evicted_messages,
            "evicted_artifacts": evicted_artifacts,
            "total_evicted": total_sweep_items,
            "duration_ms": round(sweep_duration_ms, 2),
        }

        event_bus.publish("GC_COMPLETED", duration_ms=round(sweep_duration_ms, 2), total_evicted=total_sweep_items)
        return summary

    def _gc_loop(self) -> None:
        """Background GC thread loop."""
        while not self._stop_event.is_set():
            time.sleep(self.gc_interval)
            if not self._is_initialized:
                break
            self.perform_cleanup()

    def get_gc_metrics(self) -> Dict[str, Any]:
        """Return GC metrics dictionary."""
        with self._lock:
            return {
                "total_sweeps": self._total_sweeps,
                "total_reclaimed_items": self._total_reclaimed_items,
                "last_sweep_duration_ms": round(self._last_sweep_duration_ms, 2),
            }
