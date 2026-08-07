"""
ULTRON V3 - Deterministic Service Manager
Sequential service lifecycle container managing startup ordering, graceful shutdown, health aggregation, and service restarts.
Zero external framework dependencies.
"""

import threading
import time
from typing import Dict, Any, List, Optional, Tuple

from core.config import config
from core.exceptions import BusException
from core.interfaces import IService
from core.logger import logger


class ServiceRegistration:
    """Service lifecycle metadata container."""

    def __init__(self, name: str, instance: IService, dependencies: Optional[List[str]] = None) -> None:
        self.name = name
        self.instance = instance
        self.dependencies = dependencies or []
        self.is_running = False
        self.startup_time_ms = 0.0
        self.shutdown_time_ms = 0.0


class ServiceManager(IService):
    """
    Deterministic Service Lifecycle Manager.
    
    Purpose:
    - Manages sequential initialization, health aggregation, and reverse-order shutdown for system services.
    
    Responsibilities:
    - Enforces service startup ordering based on dependency graphs.
    - Measures individual service startup and shutdown timings.
    - Aggregates health telemetry reports from all registered services.
    - Supports dynamic service restarts for failed component recovery.
    
    Thread-Safety:
    - All service registrations, initializations, shutdowns, and health checks are guarded by an RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._services: Dict[str, ServiceRegistration] = {}
        self._startup_order: List[str] = []
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize all registered services in dependency order."""
        self.initialize_all()

    def shutdown(self) -> None:
        """Shutdown all registered services in reverse dependency order."""
        self.shutdown_all()

    def health_check(self) -> Dict[str, Any]:
        """Return aggregated health status of all registered services."""
        return self.health_check_all()

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Propagate configuration settings to all registered configurable services."""
        with self._lock:
            for s_reg in self._services.values():
                if hasattr(s_reg.instance, "configure"):
                    try:
                        s_reg.instance.configure(config_data)
                    except Exception as ex:
                        logger.error(f"[ServiceManager] Error configuring service '{s_reg.name}': {ex}")

    def register_service(self, name: str, instance: IService, dependencies: Optional[List[str]] = None) -> None:
        """
        Register a service instance with explicit dependency names.
        
        Args:
            name (str): Unique service registration name.
            instance (IService): Service instance implementing IService interface.
            dependencies (Optional[List[str]]): Optional list of prerequisite service names.
        """
        if not instance or not isinstance(instance, IService):
            raise BusException(f"Service '{name}' must implement the IService contract.")

        with self._lock:
            if name in self._services:
                raise BusException(f"Service '{name}' is already registered.")

            s_reg = ServiceRegistration(name, instance, dependencies)
            self._services[name] = s_reg
            self._startup_order.append(name)
            logger.info(f"[ServiceManager] Registered service '{name}'.")

    def initialize_all(self) -> Dict[str, float]:
        """
        Initialize all registered services in sequential startup order.
        
        Returns:
            Dict[str, float]: Mapping of service names to startup duration in milliseconds.
        """
        with self._lock:
            if self._is_initialized:
                return {}

            timings: Dict[str, float] = {}
            logger.info("[ServiceManager] Starting sequential service initialization...")

            for s_name in self._startup_order:
                s_reg = self._services[s_name]

                # Verify dependencies are initialized first
                for dep in s_reg.dependencies:
                    if dep in self._services and not self._services[dep].is_running:
                        raise BusException(f"Cannot initialize service '{s_name}': Prerequisite dependency '{dep}' is not running.")

                start_t = time.time()
                try:
                    s_reg.instance.initialize()
                    s_reg.is_running = True
                    exec_ms = round((time.time() - start_t) * 1000.0, 2)
                    s_reg.startup_time_ms = exec_ms
                    timings[s_name] = exec_ms
                    logger.info(f"[ServiceManager] Initialized service '{s_name}' in {exec_ms} ms.")
                except Exception as ex:
                    logger.error(f"[ServiceManager] Failed to initialize service '{s_name}': {ex}")
                    raise BusException(f"Service startup failed for '{s_name}': {ex}")

            self._is_initialized = True
            logger.info("[ServiceManager] All services initialized successfully.")
            return timings

    def shutdown_all(self) -> Dict[str, float]:
        """
        Shutdown all running services in reverse startup order.
        
        Returns:
            Dict[str, float]: Mapping of service names to shutdown duration in milliseconds.
        """
        with self._lock:
            if not self._is_initialized and not any(s.is_running for s in self._services.values()):
                return {}

            timings: Dict[str, float] = {}
            logger.info("[ServiceManager] Executing reverse-order service shutdown...")

            # Reverse order for teardown
            for s_name in reversed(self._startup_order):
                s_reg = self._services.get(s_name)
                if s_reg and s_reg.is_running:
                    start_t = time.time()
                    try:
                        s_reg.instance.shutdown()
                    except Exception as ex:
                        logger.error(f"[ServiceManager] Error shutting down service '{s_name}': {ex}")
                    finally:
                        s_reg.is_running = False
                        exec_ms = round((time.time() - start_t) * 1000.0, 2)
                        s_reg.shutdown_time_ms = exec_ms
                        timings[s_name] = exec_ms
                        logger.info(f"[ServiceManager] Shutdown service '{s_name}' in {exec_ms} ms.")

            self._is_initialized = False
            logger.info("[ServiceManager] All services shutdown cleanly.")
            return timings

    def health_check_all(self) -> Dict[str, Any]:
        """
        Aggregate health status reports across all registered services.
        
        Returns:
            Dict[str, Any]: Comprehensive health summary dictionary.
        """
        with self._lock:
            all_healthy = True
            reports: Dict[str, Any] = {}

            for s_name, s_reg in self._services.items():
                if not s_reg.is_running:
                    all_healthy = False
                    reports[s_name] = {"status": "STOPPED", "healthy": False}
                    continue

                try:
                    h_report = s_reg.instance.health_check()
                    reports[s_name] = h_report
                    if not h_report.get("healthy", False):
                        all_healthy = False
                except Exception as ex:
                    all_healthy = False
                    reports[s_name] = {"status": "ERROR", "healthy": False, "error": str(ex)}

            return {
                "overall_status": "HEALTHY" if (all_healthy and self._is_initialized) else "DEGRADED",
                "overall_healthy": all_healthy and self._is_initialized,
                "services": reports,
            }

    def restart_service(self, name: str) -> bool:
        """
        Restart a single target service cleanly.
        
        Args:
            name (str): Target service name.
            
        Returns:
            bool: True if restarted successfully.
        """
        with self._lock:
            s_reg = self._services.get(name)
            if not s_reg:
                return False

            logger.info(f"[ServiceManager] Restarting service '{name}'...")
            try:
                if s_reg.is_running:
                    s_reg.instance.shutdown()
                    s_reg.is_running = False

                s_reg.instance.initialize()
                s_reg.is_running = True
                logger.info(f"[ServiceManager] Restarted service '{name}' successfully.")
                return True
            except Exception as ex:
                logger.error(f"[ServiceManager] Failed to restart service '{name}': {ex}")
                s_reg.is_running = False
                return False

    def get_service(self, name: str) -> Optional[IService]:
        """Retrieve registered service instance by name."""
        with self._lock:
            s_reg = self._services.get(name)
            return s_reg.instance if s_reg else None
