"""
ULTRON V3 - Subagent Health Monitor
Subagent heartbeat inspector, failure tracking, circuit breaker manager, and health snapshot exporter.
Zero external framework dependencies.
"""

import threading
import time
from typing import Dict, Any, Optional

from core.config import config
from core.event_bus import event_bus
from core.interfaces import IService
from core.logger import logger
from brain.bus_types import CircuitBreakerState


class HealthMonitor(IService):
    """
    Subagent Health Monitor and Circuit Breaker.
    
    Purpose:
    - Monitors subagent liveness via periodic heartbeats and manages circuit breaker trip states.
    
    Responsibilities:
    - Tracks agent heartbeats and failure counts.
    - Runs a background inspection loop evaluating timeout thresholds.
    - Controls circuit breaker transitions (CLOSED -> OPEN -> HALF_OPEN).
    - Exports health telemetry snapshots.
    
    Thread-Safety:
    - All state updates and inspection sweeps are guarded by an RLock.
    """

    def __init__(
        self,
        inspection_interval: Optional[float] = None,
        heartbeat_timeout: Optional[float] = None,
        failure_threshold: Optional[int] = None,
    ) -> None:
        self._lock = threading.RLock()
        # Read parameters from core/config.py
        self.inspection_interval = inspection_interval or getattr(config, "HEALTH_MONITOR_INSPECTION_INTERVAL", 5.0)
        self.heartbeat_timeout = heartbeat_timeout or getattr(config, "HEALTH_MONITOR_HEARTBEAT_TIMEOUT", 15.0)
        self.failure_threshold = failure_threshold or getattr(config, "HEALTH_MONITOR_FAILURE_THRESHOLD", 3)

        self._heartbeats: Dict[str, float] = {}
        self._failures: Dict[str, int] = {}
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._stop_event = threading.Event()
        self._inspector_thread: Optional[threading.Thread] = None
        self._is_initialized = False

    def initialize(self) -> None:
        """Start the health monitor background thread."""
        with self._lock:
            if self._is_initialized:
                return
            self._is_initialized = True
            self._stop_event.clear()

            self._inspector_thread = threading.Thread(
                target=self._inspection_loop,
                name="AgentHealthMonitorInspector",
                daemon=True,
            )
            self._inspector_thread.start()
            logger.info(f"[HealthMonitor] Started with inspection_interval={self.inspection_interval}s, timeout={self.heartbeat_timeout}s.")

    def shutdown(self) -> None:
        """Stop background inspection thread and clean up state."""
        with self._lock:
            if not self._is_initialized:
                return
            self._is_initialized = False
            self._stop_event.set()

        if self._inspector_thread:
            self._inspector_thread.join(timeout=2.0)

        with self._lock:
            self._heartbeats.clear()
            self._failures.clear()
            self._circuit_breakers.clear()

        logger.info("[HealthMonitor] Cleanly shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return HealthMonitor operational status."""
        with self._lock:
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "monitored_agents_count": len(self._heartbeats),
                "open_circuit_breakers": sum(1 for s in self._circuit_breakers.values() if s == CircuitBreakerState.OPEN),
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration parameters."""
        with self._lock:
            if "inspection_interval" in config_data:
                self.inspection_interval = float(config_data["inspection_interval"])
            if "heartbeat_timeout" in config_data:
                self.heartbeat_timeout = float(config_data["heartbeat_timeout"])
            if "failure_threshold" in config_data:
                self.failure_threshold = int(config_data["failure_threshold"])

    def register_monitored_agent(self, agent_id: str) -> None:
        """Register a subagent for health monitoring."""
        with self._lock:
            now = time.time()
            self._heartbeats[agent_id] = now
            self._failures[agent_id] = 0
            self._circuit_breakers[agent_id] = CircuitBreakerState.CLOSED

    def unregister_monitored_agent(self, agent_id: str) -> None:
        """Unregister a subagent from health monitoring."""
        with self._lock:
            self._heartbeats.pop(agent_id, None)
            self._failures.pop(agent_id, None)
            self._circuit_breakers.pop(agent_id, None)

    def heartbeat(self, agent_id: str) -> None:
        """Record a heartbeat timestamp for a subagent."""
        with self._lock:
            now = time.time()
            self._heartbeats[agent_id] = now
            if agent_id not in self._circuit_breakers:
                self._circuit_breakers[agent_id] = CircuitBreakerState.CLOSED
                self._failures[agent_id] = 0

    def record_failure(self, agent_id: str, reason: str) -> None:
        """Record a failure occurrence for a subagent and check circuit breaker threshold."""
        with self._lock:
            current_failures = self._failures.get(agent_id, 0) + 1
            self._failures[agent_id] = current_failures

            if current_failures >= self.failure_threshold:
                if self._circuit_breakers.get(agent_id) != CircuitBreakerState.OPEN:
                    self._circuit_breakers[agent_id] = CircuitBreakerState.OPEN
                    event_bus.publish("CIRCUIT_BREAKER_TRIPPED", agent_id=agent_id, reason=reason, failures=current_failures)
                    logger.error(f"[HealthMonitor] Circuit breaker OPENED for agent '{agent_id}' after {current_failures} failures.")

    def get_circuit_breaker_state(self, agent_id: str) -> CircuitBreakerState:
        """Get circuit breaker state for a subagent."""
        with self._lock:
            return self._circuit_breakers.get(agent_id, CircuitBreakerState.CLOSED)

    def reset_circuit_breaker(self, agent_id: str) -> None:
        """Reset circuit breaker state back to CLOSED."""
        with self._lock:
            self._failures[agent_id] = 0
            self._circuit_breakers[agent_id] = CircuitBreakerState.CLOSED

    def get_health_snapshot(self) -> Dict[str, Any]:
        """
        Export a health snapshot of all monitored subagents.
        
        Returns:
            Dict[str, Any]: Health snapshot containing heartbeats, failure counts, and circuit breaker states.
        """
        with self._lock:
            now = time.time()
            snapshot = {}
            for agent_id, last_hb in self._heartbeats.items():
                age = round(now - last_hb, 2)
                snapshot[agent_id] = {
                    "last_heartbeat_age_sec": age,
                    "failures": self._failures.get(agent_id, 0),
                    "circuit_breaker": self._circuit_breakers.get(agent_id, CircuitBreakerState.CLOSED).value,
                    "healthy": age <= self.heartbeat_timeout and self._circuit_breakers.get(agent_id) == CircuitBreakerState.CLOSED,
                }
            return snapshot

    def inspect_health(self) -> Dict[str, Any]:
        """Manually trigger a health inspection sweep and return results."""
        self._perform_health_inspection()
        return self.get_health_snapshot()

    def _inspection_loop(self) -> None:
        """Background health inspection sweep loop."""
        while not self._stop_event.is_set():
            time.sleep(self.inspection_interval)
            if not self._is_initialized:
                break
            self._perform_health_inspection()

    def _perform_health_inspection(self) -> None:
        """Internal inspection sweep logic."""
        now = time.time()
        with self._lock:
            for agent_id, last_hb in list(self._heartbeats.items()):
                age = now - last_hb
                if age > self.heartbeat_timeout:
                    logger.warning(f"[HealthMonitor] Agent '{agent_id}' heartbeat missing ({age:.1f}s > {self.heartbeat_timeout}s).")
                    event_bus.publish("AGENT_UNHEALTHY", agent_id=agent_id, age=round(age, 2))
                    self.record_failure(agent_id, f"Heartbeat missing for {age:.1f}s")
