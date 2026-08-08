from __future__ import annotations
"""
ULTRON V3 - Central Agent Manager
Master lifecycle supervisor, registration authority, capability discovery, task dispatcher, and health inspector for all Phase 2B Ultron agents.
Reuses Phase 2A AgentMemoryBus, ServiceManager, AgentRegistry, HealthMonitor, and MetricsTelemetry.
"""

import threading
from typing import Dict, Any, List, Optional, Type, TYPE_CHECKING

from core.config import config
from core.interfaces import IService
from core.logger import logger
from brain.agent_bus import AgentMemoryBus
from brain.bus_types import CircuitBreakerState, AgentStatus

if TYPE_CHECKING:
    from agents.base_ultron_agent import BaseUltronAgent


class AgentManager(IService):
    """
    Central Agent Manager Supervisor for Phase 2B.
    
    Purpose:
    - Provides lifecycle management, registration, lookup, health monitoring, capability discovery,
      and task dispatching for all registered Ultron agents.
      
    Responsibilities:
    - Holds references to all registered BaseUltronAgent instances.
    - Manages top-level startup and graceful shutdown sequence for agents.
    - Integrates with Phase 2A AgentMemoryBus facade.
    - Enforces circuit breaker checks before dispatching tasks to subagents.
    """

    def __init__(self, bus: Optional[AgentMemoryBus] = None) -> None:
        self._lock = threading.RLock()
        self.bus = bus or AgentMemoryBus()
        self._agents: Dict[str, BaseUltronAgent] = {}
        self._is_initialized = False

    def register_agent(self, agent: BaseUltronAgent) -> bool:
        """
        Register an agent instance with AgentManager, AgentMemoryBus, and legacy AgentRegistry.
        Rejects duplicate registrations with identical agent_id.
        """
        with self._lock:
            agent_id = agent.agent_id
            name_lower = agent.name.lower()

            # Check duplicate agent_id or name
            if agent_id in self._agents:
                logger.warning(f"[AgentManager] Registration rejected: Duplicate agent_id '{agent_id}'.")
                return False

            for existing in self._agents.values():
                if existing.name.lower() == name_lower:
                    logger.warning(f"[AgentManager] Registration rejected: Duplicate agent name '{agent.name}'.")
                    return False

            # Attach bus reference to agent
            agent.bus = self.bus
            self._agents[agent_id] = agent

            # Register manifest with Phase 2A AgentMemoryBus
            try:
                self.bus.register_agent(agent.get_manifest())
            except Exception as err:
                logger.debug(f"[AgentManager] Bus manifest registration notice for '{agent_id}': {err}")

            # Register with legacy agents.registry singleton for backward compatibility
            try:
                from agents.registry import agent_registry
                agent_registry._agents[name_lower] = agent
            except Exception as err:
                logger.debug(f"[AgentManager] Legacy registry notice for '{agent_id}': {err}")

            # Initialize immediately if AgentManager is already active
            if self._is_initialized:
                try:
                    agent.initialize()
                except Exception as err:
                    logger.error(f"[AgentManager] Error initializing agent '{agent_id}': {err}")

            logger.info(f"[AgentManager] Successfully registered agent '{agent.name}' (ID: '{agent_id}').")
            return True

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister and shutdown an agent cleanly."""
        with self._lock:
            agent = self._agents.pop(agent_id, None)
            if not agent:
                return False

            try:
                agent.shutdown()
            except Exception as err:
                logger.warning(f"[AgentManager] Error shutting down agent '{agent_id}': {err}")

            try:
                self.bus.unregister_agent(agent_id)
            except Exception as err:
                logger.debug(f"[AgentManager] Bus unregister notice for '{agent_id}': {err}")

            logger.info(f"[AgentManager] Unregistered agent '{agent_id}'.")
            return True

    def get_agent(self, agent_id_or_name: str) -> Optional[BaseUltronAgent]:
        """Fetch registered agent instance by agent_id or name."""
        with self._lock:
            target = agent_id_or_name.lower().strip()
            if target in self._agents:
                return self._agents[target]

            for agent in self._agents.values():
                if agent.agent_id.lower() == target or agent.name.lower() == target:
                    return agent
            return None

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return list of manifest summaries and health status for all registered agents."""
        with self._lock:
            result = []
            for agent in self._agents.values():
                result.append({
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "version": agent.version,
                    "status": agent.status.value,
                    "capabilities": list(agent.capabilities),
                    "supported_skills": list(agent.supported_skills),
                })
            return result

    def find_agents_by_capability(self, capability: str) -> List[BaseUltronAgent]:
        """Find active healthy agents supporting specified capability."""
        with self._lock:
            matched = []
            cap_lower = capability.lower().strip()
            for agent in self._agents.values():
                agent_caps = [c.lower() for c in agent.capabilities]
                if cap_lower in agent_caps and agent.status in [AgentStatus.ONLINE, AgentStatus.BUSY]:
                    matched.append(agent)
            return matched

    # -------------------------------------------------------------------------
    # ISERVICE LIFECYCLE MANAGEMENT
    # -------------------------------------------------------------------------
    def initialize(self) -> None:
        """Initialize AgentMemoryBus and all registered agents sequentially."""
        with self._lock:
            if self._is_initialized:
                return

            logger.info("[AgentManager] Initializing AgentManager and AgentMemoryBus...")
            self.bus.initialize()

            for agent_id, agent in self._agents.items():
                try:
                    agent.initialize()
                except Exception as err:
                    logger.error(f"[AgentManager] Error initializing agent '{agent_id}': {err}")

            self._is_initialized = True
            logger.info(f"[AgentManager] AgentManager initialized cleanly with {len(self._agents)} agents.")

    def shutdown(self) -> None:
        """Shutdown all managed agents and release AgentMemoryBus resources."""
        with self._lock:
            if not self._is_initialized:
                return

            logger.info("[AgentManager] Shutting down all managed agents...")
            for agent_id, agent in list(self._agents.items()):
                try:
                    agent.shutdown()
                except Exception as err:
                    logger.warning(f"[AgentManager] Error shutting down agent '{agent_id}': {err}")

            self.bus.shutdown()
            if hasattr(self, "_executor") and self._executor:
                self._executor.shutdown(wait=False)
            self._is_initialized = False
            logger.info("[AgentManager] AgentManager shutdown complete.")

    def health_check(self) -> Dict[str, Any]:
        """Return aggregated health telemetry report for all managed agents and bus."""
        with self._lock:
            agent_healths = {aid: ag.health_check() for aid, ag in self._agents.items()}
            all_healthy = self._is_initialized and all(ah.get("healthy", False) for ah in agent_healths.values())

            return {
                "status": "HEALTHY" if all_healthy else ("DEGRADED" if self._is_initialized else "STOPPED"),
                "healthy": all_healthy,
                "agents_count": len(self._agents),
                "agent_health": agent_healths,
                "bus_health": self.bus.health_check(),
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Propagate configuration settings to AgentMemoryBus and all managed agents."""
        with self._lock:
            self.bus.configure(config_data)
            for agent in self._agents.values():
                agent.configure(config_data)

    # -------------------------------------------------------------------------
    # TASK DISPATCH & CONTROL
    # -------------------------------------------------------------------------
    def dispatch_task(self, target: str, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch a task to an agent matched by agent_id or capability.
        Enforces circuit breaker checks before execution.
        """
        agent = self.get_agent(target)
        if not agent:
            matched = self.find_agents_by_capability(target)
            if matched:
                agent = matched[0]

        if not agent:
            logger.warning(f"[AgentManager] Dispatch failed: No agent found for target '{target}'.")
            return {"status": "ERROR", "error": f"No agent found matching target '{target}'."}

        # Check HealthMonitor Circuit Breaker State
        circuit_state = self.bus.get_circuit_breaker_state(agent.agent_id)
        if circuit_state == CircuitBreakerState.OPEN:
            logger.warning(f"[AgentManager] Dispatch rejected: Circuit breaker OPEN for agent '{agent.agent_id}'.")
            return {
                "status": "ERROR",
                "error": f"Circuit breaker OPEN for agent '{agent.agent_id}'. Task rejected for health recovery.",
            }

        logger.info(f"[AgentManager] Dispatching task '{task_id}' to agent '{agent.name}' (ID: '{agent.agent_id}').")
        return agent.execute_task(task_id, payload)

    def cancel_task(self, task_id: str, agent_id: Optional[str] = None) -> bool:
        """Cancel an active task on specified agent or across all managed agents."""
        with self._lock:
            if agent_id:
                agent = self.get_agent(agent_id)
                return agent.cancel_task(task_id) if agent else False

            cancelled = False
            for agent in self._agents.values():
                if agent.cancel_task(task_id):
                    cancelled = True
            return cancelled


# Global AgentManager Singleton instance
agent_manager = AgentManager()
