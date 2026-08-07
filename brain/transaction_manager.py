"""
ULTRON V3 - Workspace Transaction Manager
Optimistic concurrency transaction manager for workspace operations with conflict detection and telemetry.
Zero external framework dependencies.
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from core.config import config
from core.event_bus import event_bus
from core.exceptions import WorkspaceConflictException, BusException
from core.logger import logger
from brain.workspace_store import WorkspaceStore


@dataclass
class TransactionContext:
    """Optimistic transaction execution context envelope."""
    tx_id: str
    agent_id: str
    task_id: str
    created_at: float
    timeout: float
    staged_writes: Dict[str, Any] = field(default_factory=dict)
    snapshot_versions: Dict[str, int] = field(default_factory=dict)
    is_active: bool = True


from core.interfaces import IService


class TransactionManager(IService):
    """
    Optimistic Transaction Manager.
    
    Purpose:
    - Provides ACID-like staged writes and optimistic version locking for workspace modifications.
    
    Responsibilities:
    - Creates isolated `TransactionContext` objects.
    - Stages non-blocking workspace key writes.
    - Validates snapshot versions during commit and rolls back staged writes on conflict.
    - Publishes transaction lifecycle events and exports transaction telemetry metrics.
    
    Thread-Safety:
    - All context creations, commits, rollbacks, and metrics updates are guarded by an RLock.
    """

    def __init__(self, workspace_store: Optional[WorkspaceStore] = None) -> None:
        self._lock = threading.RLock()
        self.workspace_store = workspace_store or WorkspaceStore()
        self.default_timeout = getattr(config, "WORKSPACE_TRANSACTION_TIMEOUT", 10.0)

        # Active transactions index
        self._active_txs: Dict[str, TransactionContext] = {}

        # Telemetry metrics counters
        self._total_committed = 0
        self._total_rolled_back = 0
        self._total_conflicts = 0
        self._total_expired = 0
        self._total_commit_time_ms = 0.0
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize TransactionManager."""
        with self._lock:
            if self._is_initialized:
                return
            self._is_initialized = True
            logger.info("[TransactionManager] Initialized cleanly.")

    def shutdown(self) -> None:
        """Shutdown TransactionManager."""
        with self._lock:
            self._active_txs.clear()
            self._is_initialized = False
            logger.info("[TransactionManager] Shutdown cleanly.")

    def health_check(self) -> Dict[str, Any]:
        """Return health status."""
        with self._lock:
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "active_transactions": len(self._active_txs),
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Configure TransactionManager."""
        with self._lock:
            if "timeout" in config_data:
                self.default_timeout = float(config_data["timeout"])
        self._conflict_count = 0
        self._expired_count = 0
        self._total_commit_time_ms = 0.0

    def begin_transaction(
        self,
        agent_id: str,
        task_id: str,
        timeout: Optional[float] = None,
    ) -> TransactionContext:
        """
        Begin a new optimistic transaction.
        
        Args:
            agent_id (str): Subagent starting transaction.
            task_id (str): Scoped task ID.
            timeout (Optional[float]): Custom timeout in seconds.
            
        Returns:
            TransactionContext: New active transaction context object.
        """
        with self._lock:
            tx_id = f"tx_{uuid.uuid4().hex[:12]}"
            tx_timeout = timeout or self.default_timeout
            now = time.time()

            tx = TransactionContext(
                tx_id=tx_id,
                agent_id=agent_id,
                task_id=task_id,
                created_at=now,
                timeout=tx_timeout,
            )

            self._active_txs[tx_id] = tx
            logger.info(f"[TransactionManager] Began transaction '{tx_id}' for agent '{agent_id}'.")
            return tx

    def staged_write(self, tx: TransactionContext, key: str, value: Any) -> None:
        """
        Stage a key-value write inside a transaction context.
        
        Args:
            tx (TransactionContext): Target active transaction context.
            key (str): Target workspace key.
            value (Any): Payload value.
        """
        with self._lock:
            self._verify_active(tx)
            
            # Record current version snapshot for conflict detection on commit
            if key not in tx.snapshot_versions:
                entry = self.workspace_store.get_entry(key)
                tx.snapshot_versions[key] = entry.version if entry else 0

            tx.staged_writes[key] = value

    def commit(self, tx: TransactionContext) -> bool:
        """
        Commit staged writes atomically to the workspace store.
        
        Args:
            tx (TransactionContext): Target active transaction context.
            
        Returns:
            bool: True if committed successfully.
            
        Raises:
            WorkspaceConflictException: If optimistic version conflict is detected.
        """
        start_time = time.time()
        with self._lock:
            self._verify_active(tx)

            # 1. Conflict Detection: Verify snapshot versions against current store versions
            for key, snap_v in tx.snapshot_versions.items():
                current_entry = self.workspace_store.get_entry(key)
                current_v = current_entry.version if current_entry else 0
                if snap_v != current_v:
                    self._conflict_count += 1
                    self.rollback(tx)
                    raise WorkspaceConflictException(
                        f"Version conflict on key '{key}': Staged snapshot v{snap_v} != current v{current_v}."
                    )

            # 2. Apply Staged Writes
            for key, val in tx.staged_writes.items():
                self.workspace_store.write(
                    key=key,
                    value=val,
                    owner_agent=tx.agent_id,
                    task_id=tx.task_id,
                )

            tx.is_active = False
            self._active_txs.pop(tx.tx_id, None)

            # Telemetry Metrics Update
            exec_time_ms = (time.time() - start_time) * 1000.0
            self._total_committed += 1
            self._total_commit_time_ms += exec_time_ms

            event_bus.publish("TRANSACTION_COMMITTED", tx_id=tx.tx_id, agent_id=tx.agent_id, keys=list(tx.staged_writes.keys()))
            logger.info(f"[TransactionManager] Committed transaction '{tx.tx_id}'.")
            return True

    def rollback(self, tx: TransactionContext) -> None:
        """
        Rollback and discard all staged writes inside a transaction.
        
        Args:
            tx (TransactionContext): Target active transaction context.
        """
        with self._lock:
            if not tx.is_active:
                return

            tx.staged_writes.clear()
            tx.is_active = False
            self._active_txs.pop(tx.tx_id, None)
            self._total_rolled_back += 1

            event_bus.publish("TRANSACTION_ROLLED_BACK", tx_id=tx.tx_id, agent_id=tx.agent_id)
            logger.info(f"[TransactionManager] Rolled back transaction '{tx.tx_id}'.")

    def is_expired(self, tx: TransactionContext) -> bool:
        """Check if a transaction context has exceeded its timeout limit."""
        return (time.time() - tx.created_at) > tx.timeout

    def _verify_active(self, tx: TransactionContext) -> None:
        """Internal helper to verify transaction state."""
        if not tx.is_active:
            raise BusException(f"Transaction '{tx.tx_id}' is no longer active.")
        if self.is_expired(tx):
            self._expired_count += 1
            self.rollback(tx)
            raise BusException(f"Transaction '{tx.tx_id}' has expired (Timeout: {tx.timeout}s).")

    def get_transaction_metrics(self) -> Dict[str, Any]:
        """
        Return telemetry metrics for active and completed transactions.
        
        Returns:
            Dict[str, Any]: Transaction telemetry summary dictionary.
        """
        with self._lock:
            avg_commit_ms = (
                round(self._total_commit_time_ms / self._total_committed, 2)
                if self._total_committed > 0
                else 0.0
            )
            return {
                "active_transactions": len(self._active_txs),
                "committed_transactions": self._total_committed,
                "rolled_back_transactions": self._total_rolled_back,
                "conflict_count": self._conflict_count,
                "expired_transactions": self._expired_count,
                "average_commit_time_ms": avg_commit_ms,
            }
