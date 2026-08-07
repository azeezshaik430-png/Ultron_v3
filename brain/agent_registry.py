"""
ULTRON V3 - Subagent Registry
Thread-safe subagent registration, capability index, and status tracking.
Zero external framework dependencies.
"""

import threading
from typing import Dict, Any, List, Optional, Set

from core.event_bus import event_bus
from core.interfaces import IService
from core.logger import logger
from brain.bus_types import AgentManifest, AgentStatus


class AgentRegistry(IService):
    """
    Subagent Registry and Capability Index.
    
    Purpose:
    - Centralizes subagent metadata registration, capability lookup, and status tracking.
    
    Responsibilities:
    - Registers subagent manifests and maintains an $O(1)$ capability index.
    - Tracks subagent health status transitions.
    - Exports registry telemetry metrics.
    
    Thread-Safety:
    - All registration, lookup, status update, and removal operations are guarded by an RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._agents: Dict[str, AgentManifest] = {}
        self._statuses: Dict[str, AgentStatus] = {}
        self._capability_index: Dict[str, Set[str]] = {}
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize the agent registry."""
        with self._lock:
            if self._is_initialized:
                return
            self._is_initialized = True
            logger.info("[AgentRegistry] Subagent Registry initialized.")

    def shutdown(self) -> None:
        """Release registry state on system shutdown."""
        with self._lock:
            self._agents.clear()
            self._statuses.clear()
            self._capability_index.clear()
            self._is_initialized = False
            logger.info("[AgentRegistry] Subagent Registry cleanly shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return registry health telemetry status."""
        with self._lock:
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "registered_agents_count": len(self._agents),
                "metrics": self.get_registry_metrics(),
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration settings."""
        pass

    def register_agent(self, manifest: AgentManifest) -> bool:
        """
        Register a subagent manifest and index its capabilities.
        If agent_id is already registered, updates manifest cleanly.
        
        Args:
            manifest (AgentManifest): Subagent manifest object.
            
        Returns:
            bool: True if registration succeeded.
        """
        if not manifest or not manifest.agent_id:
            return False

        with self._lock:
            agent_id = manifest.agent_id
            is_duplicate = agent_id in self._agents

            if is_duplicate:
                # Cleanly un-index old capabilities first
                old_manifest = self._agents[agent_id]
                for cap in old_manifest.capabilities:
                    if cap in self._capability_index:
                        self._capability_index[cap].discard(agent_id)

            self._agents[agent_id] = manifest
            self._statuses[agent_id] = AgentStatus.ONLINE

            # Index capabilities
            for cap in manifest.capabilities:
                if cap not in self._capability_index:
                    self._capability_index[cap] = set()
                self._capability_index[cap].add(agent_id)

            event_bus.publish("AGENT_REGISTERED", agent_id=agent_id, name=manifest.name, duplicate=is_duplicate)
            logger.info(f"[AgentRegistry] Registered agent '{agent_id}' ({manifest.name}).")
            return True

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister a subagent and remove its capability index entries.
        
        Args:
            agent_id (str): Target subagent ID.
            
        Returns:
            bool: True if removed, False if agent was not present.
        """
        with self._lock:
            if agent_id not in self._agents:
                return False

            manifest = self._agents.pop(agent_id)
            self._statuses.pop(agent_id, None)

            for cap in manifest.capabilities:
                if cap in self._capability_index:
                    self._capability_index[cap].discard(agent_id)
                    if not self._capability_index[cap]:
                        del self._capability_index[cap]

            event_bus.publish("AGENT_UNREGISTERED", agent_id=agent_id)
            logger.info(f"[AgentRegistry] Unregistered agent '{agent_id}'.")
            return True

    def get_agent(self, agent_id: str) -> Optional[AgentManifest]:
        """Retrieve registered agent manifest by ID."""
        with self._lock:
            return self._agents.get(agent_id)

    def find_agents_by_capability(self, capability: str) -> List[AgentManifest]:
        """
        Find all active subagents supporting a specific capability string.
        
        Args:
            capability (str): Capability keyword.
            
        Returns:
            List[AgentManifest]: List of matching subagent manifests.
        """
        with self._lock:
            agent_ids = self._capability_index.get(capability, set())
            return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def update_status(self, agent_id: str, status: AgentStatus) -> None:
        """Update subagent operational status."""
        with self._lock:
            if agent_id in self._agents:
                self._statuses[agent_id] = status
                event_bus.publish("AGENT_STATUS_UPDATED", agent_id=agent_id, status=status.value)

    def get_status(self, agent_id: str) -> Optional[AgentStatus]:
        """Get subagent operational status."""
        with self._lock:
            return self._statuses.get(agent_id)

    def get_all_agents(self) -> List[AgentManifest]:
        """Return list of all registered subagent manifests."""
        with self._lock:
            return list(self._agents.values())

    def get_registry_metrics(self) -> Dict[str, int]:
        """
        Return telemetry status count metrics.
        
        Returns:
            Dict[str, int]: Counts for total, online, busy, offline, and unhealthy agents.
        """
        with self._lock:
            total = len(self._agents)
            online = 0
            busy = 0
            offline = 0
            unhealthy = 0

            for st in self._statuses.values():
                if st == AgentStatus.ONLINE:
                    online += 1
                elif st == AgentStatus.BUSY:
                    busy += 1
                elif st == AgentStatus.OFFLINE:
                    offline += 1
                elif st in [AgentStatus.UNHEALTHY, AgentStatus.DEGRADED]:
                    unhealthy += 1

            return {
                "total_agents": total,
                "online_agents": online,
                "busy_agents": busy,
                "offline_agents": offline,
                "unhealthy_agents": unhealthy,
            }
