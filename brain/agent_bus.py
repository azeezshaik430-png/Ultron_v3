"""
ULTRON V3 - Master Agent Memory Bus Facade
Unified production facade exposing versioned Agent Bus APIs, workspace operations, reliable messaging,
transactions, ACL, scratchpad, artifacts, recovery journal, garbage collection, and telemetry metrics.
Zero duplicated business logic - pure delegation facade.
"""

import threading
from typing import Dict, Any, List, Optional

from core.interfaces import IService
from core.logger import logger
from brain.bus_types import (
    AgentManifest,
    AgentMessage,
    AgentStatus,
    ArtifactMetadata,
    CircuitBreakerState,
    ScratchpadEntry,
    WorkspaceEntry,
)
from brain.agent_registry import AgentRegistry
from brain.health_monitor import HealthMonitor
from brain.workspace_store import WorkspaceStore
from brain.workspace_acl import WorkspaceACL, AccessTier, PermissionType
from brain.transaction_manager import TransactionManager, TransactionContext
from brain.message_router import AgentMessageRouter
from brain.scratchpad import AgentScratchpad
from brain.artifact_registry import ArtifactRegistry
from brain.recovery_journal import RecoveryJournal
from brain.garbage_collector import BusGarbageCollector
from brain.metrics_telemetry import MetricsTelemetry
from brain.service_manager import ServiceManager


class AgentMemoryBus(IService):
    """
    Master Agent Memory Bus Facade.
    
    Purpose:
    - Centralizes access to all Phase 2A memory bus subsystems through a clean facade API.
    
    Responsibilities:
    - Instantiates underlying subsystem implementations and registers them with ServiceManager.
    - Exposes non-duplicative facade APIs delegating to workspace, messaging, registry, recovery, and telemetry services.
    - Manages top-level lifecycle initialization and graceful shutdown.
    
    Thread-Safety:
    - All subsystem delegations are thread-safe and guarded by internal RLock contexts.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.service_manager = ServiceManager()

        # Instantiate Subsystems
        self.agent_registry = AgentRegistry()
        self.health_monitor = HealthMonitor()
        self.workspace_acl = WorkspaceACL()
        self.workspace_store = WorkspaceStore(acl=self.workspace_acl)
        self.transaction_manager = TransactionManager(workspace_store=self.workspace_store)
        self.message_router = AgentMessageRouter()
        self.scratchpad = AgentScratchpad()
        self.artifact_registry = ArtifactRegistry()
        self.recovery_journal = RecoveryJournal()
        self.garbage_collector = BusGarbageCollector(
            scratchpad=self.scratchpad,
            message_router=self.message_router,
            artifact_registry=self.artifact_registry,
        )
        self.metrics_telemetry = MetricsTelemetry(
            message_router=self.message_router,
            workspace_store=self.workspace_store,
            agent_registry=self.agent_registry,
            health_monitor=self.health_monitor,
            recovery_journal=self.recovery_journal,
            garbage_collector=self.garbage_collector,
        )

        # Register Subsystems with ServiceManager in Dependency Order
        self.service_manager.register_service("AgentRegistry", self.agent_registry)
        self.service_manager.register_service("HealthMonitor", self.health_monitor, dependencies=["AgentRegistry"])
        self.service_manager.register_service("WorkspaceStore", self.workspace_store)
        self.service_manager.register_service("TransactionManager", self.transaction_manager, dependencies=["WorkspaceStore"])
        self.service_manager.register_service("MessageRouter", self.message_router)
        self.service_manager.register_service("Scratchpad", self.scratchpad)
        self.service_manager.register_service("ArtifactRegistry", self.artifact_registry)
        self.service_manager.register_service("RecoveryJournal", self.recovery_journal)
        self.service_manager.register_service("GarbageCollector", self.garbage_collector, dependencies=["Scratchpad", "MessageRouter"])
        self.service_manager.register_service("MetricsTelemetry", self.metrics_telemetry)

        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize all Agent Memory Bus subsystems sequentially via ServiceManager."""
        with self._lock:
            if self._is_initialized:
                return
            self.service_manager.initialize_all()
            self._is_initialized = True
            logger.info("[AgentMemoryBus] Master Bus Facade initialized cleanly.")

    def shutdown(self) -> None:
        """Shutdown all Agent Memory Bus subsystems in reverse order via ServiceManager."""
        with self._lock:
            if not self._is_initialized:
                return
            self.service_manager.shutdown_all()
            self._is_initialized = False
            logger.info("[AgentMemoryBus] Master Bus Facade shutdown cleanly.")

    def health_check(self) -> Dict[str, Any]:
        """Return aggregated health report of all bus subsystems."""
        return self.service_manager.health_check_all()

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Propagate configuration to all bus subsystems."""
        self.service_manager.configure(config_data)

    # -------------------------------------------------------------------------
    # 1. AGENT REGISTRY & HEALTH FACADE APIs
    # -------------------------------------------------------------------------
    def register_agent(self, manifest: AgentManifest) -> bool:
        """Register a subagent manifest."""
        res = self.agent_registry.register_agent(manifest)
        if res:
            self.health_monitor.register_monitored_agent(manifest.agent_id)
        return res

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister a subagent."""
        self.health_monitor.unregister_monitored_agent(agent_id)
        return self.agent_registry.unregister_agent(agent_id)

    def heartbeat(self, agent_id: str) -> None:
        """Record subagent heartbeat."""
        self.health_monitor.heartbeat(agent_id)

    def get_agent_status(self, agent_id: str) -> Optional[AgentStatus]:
        """Get subagent operational status."""
        return self.agent_registry.get_status(agent_id)

    def find_agents_by_capability(self, capability: str) -> List[AgentManifest]:
        """Find active subagents matching capability."""
        return self.agent_registry.find_agents_by_capability(capability)

    def get_circuit_breaker_state(self, agent_id: str) -> CircuitBreakerState:
        """Get circuit breaker state for a subagent."""
        return self.health_monitor.get_circuit_breaker_state(agent_id)

    def get_health_snapshot(self) -> Dict[str, Any]:
        """Export health snapshot of all monitored subagents."""
        return self.health_monitor.get_health_snapshot()

    # -------------------------------------------------------------------------
    # 2. WORKSPACE & ACL FACADE APIs
    # -------------------------------------------------------------------------
    def read_workspace(self, key: str, agent_id: str = "system", task_id: Optional[str] = None) -> Optional[Any]:
        """Read a workspace key value."""
        return self.workspace_store.read(key, agent_id=agent_id, task_id=task_id)

    def write_workspace(self, key: str, value: Any, owner_agent: str = "system", task_id: str = "") -> int:
        """Write or update a workspace key value."""
        return self.workspace_store.write(key, value, owner_agent=owner_agent, task_id=task_id)

    def delete_workspace(self, key: str, agent_id: str = "system") -> bool:
        """Delete a workspace key."""
        return self.workspace_store.delete(key, agent_id=agent_id)

    def exists_workspace(self, key: str) -> bool:
        """Check if a workspace key exists."""
        return self.workspace_store.exists(key)

    def grant_permission(self, key: str, agent_id: str, access_tier: AccessTier, task_id: Optional[str] = None) -> None:
        """Grant ACL permission tier to a subagent for a workspace key."""
        self.workspace_acl.grant_permission(key, agent_id, access_tier, task_id=task_id)

    def create_workspace_snapshot(self, created_by: str = "system", description: str = "") -> Dict[str, Any]:
        """Create a deep workspace snapshot."""
        return self.workspace_store.create_snapshot(created_by=created_by, description=description)

    def restore_workspace_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Restore workspace store from snapshot."""
        self.workspace_store.restore_snapshot(snapshot)

    # -------------------------------------------------------------------------
    # 3. TRANSACTION MANAGER FACADE APIs
    # -------------------------------------------------------------------------
    def begin_transaction(self, agent_id: str, task_id: str, timeout: Optional[float] = None) -> TransactionContext:
        """Begin an optimistic workspace transaction."""
        return self.transaction_manager.begin_transaction(agent_id, task_id, timeout=timeout)

    def commit_transaction(self, tx: TransactionContext) -> bool:
        """Commit staged writes in an active transaction context."""
        return self.transaction_manager.commit(tx)

    def rollback_transaction(self, tx: TransactionContext) -> None:
        """Rollback staged writes in an active transaction context."""
        self.transaction_manager.rollback(tx)

    # -------------------------------------------------------------------------
    # 4. MESSAGE ROUTER FACADE APIs
    # -------------------------------------------------------------------------
    def send_message(self, envelope: AgentMessage) -> str:
        """Send a bus message envelope."""
        return self.message_router.send_message(envelope)

    def receive_message(self, agent_id: str, timeout: float = 0.1) -> Optional[AgentMessage]:
        """Receive top priority message for a subagent inbox."""
        return self.message_router.receive_message(agent_id, timeout=timeout)

    def acknowledge_message(self, message_id: str) -> bool:
        """Acknowledge (ACK) successful processing of a message."""
        return self.message_router.acknowledge_message(message_id)

    def negative_acknowledge(self, message_id: str, reason: str = "") -> bool:
        """Negative acknowledge (NACK) message processing with retry or DLQ."""
        return self.message_router.negative_acknowledge(message_id, reason=reason)

    def get_dlq_messages(self) -> List[AgentMessage]:
        """Get list of Dead Letter Queue messages."""
        return self.message_router.get_dlq_messages()

    # -------------------------------------------------------------------------
    # 5. SCRATCHPAD & ARTIFACT FACADE APIs
    # -------------------------------------------------------------------------
    def append_scratchpad(self, task_id: str, agent_id: str, entry_text: str) -> ScratchpadEntry:
        """Append a note entry to task scratchpad."""
        return self.scratchpad.append_entry(task_id, agent_id, entry_text)

    def read_scratchpad(self, task_id: str, agent_id: Optional[str] = None) -> List[ScratchpadEntry]:
        """Read task scratchpad notes."""
        return self.scratchpad.read_scratchpad(task_id, agent_id=agent_id)

    def register_artifact(self, task_id: str, file_path: str, mime_type: str = "text/plain", owner_agent: str = "system", metadata: Optional[Dict[str, Any]] = None) -> ArtifactMetadata:
        """Register a disk file artifact."""
        return self.artifact_registry.register_artifact(task_id, file_path, mime_type=mime_type, owner_agent=owner_agent, metadata=metadata)

    def get_artifact(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        """Get registered artifact metadata."""
        return self.artifact_registry.get_artifact(artifact_id)

    # -------------------------------------------------------------------------
    # 6. RECOVERY JOURNAL, GC & METRICS FACADE APIs
    # -------------------------------------------------------------------------
    def append_journal(self, action: str, payload: Dict[str, Any]) -> bool:
        """Append event log entry to recovery journal."""
        return self.recovery_journal.append_event(action, payload)

    def checkpoint_journal(self, description: str = "") -> str:
        """Perform a journal checkpoint and create clean snapshot."""
        snp = self.create_workspace_snapshot(description=description)
        return self.recovery_journal.checkpoint(snapshot_data=snp)

    def recover(self) -> bool:
        """Execute crash recovery protocol."""
        return self.recovery_journal.recover(workspace_store=self.workspace_store)

    def run_gc(self) -> Dict[str, int]:
        """Run a manual garbage collection sweep."""
        return self.garbage_collector.perform_cleanup()

    def export_metrics(self) -> Dict[str, Any]:
        """Export unified Mission Control metrics telemetry snapshot."""
        return self.metrics_telemetry.export_metrics()
