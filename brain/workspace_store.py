"""
ULTRON V3 - Shared Workspace Store
Thread-safe versioned key-value workspace store with snapshot/restore support and event publishing.
Zero external framework dependencies.
"""

import sys
import threading
import time
import uuid
from typing import Dict, Any, List, Optional

from core.config import config
from core.event_bus import event_bus
from core.exceptions import QuotaExceededException, PermissionDeniedException
from core.interfaces import IService
from core.logger import logger
from brain.bus_types import WorkspaceEntry
from brain.workspace_acl import WorkspaceACL, PermissionType


class WorkspaceStore(IService):
    """
    Shared Workspace Key-Value Store.
    
    Purpose:
    - Centralized thread-safe key-value data workspace for subagents.
    
    Responsibilities:
    - Provides CRUD operations with monotonic version increments.
    - Enforces workspace key and value payload size quotas.
    - Manages snapshot creation and workspace restorations.
    - Publishes workspace lifecycle events over Phase 1 EventBus.
    
    Thread-Safety:
    - All workspace reads, writes, snapshots, and restorations are guarded by an RLock.
    """

    def __init__(
        self,
        max_keys: Optional[int] = None,
        max_value_size: Optional[int] = None,
        max_snapshots: Optional[int] = None,
        acl: Optional[WorkspaceACL] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.max_keys = max_keys or getattr(config, "WORKSPACE_MAX_KEYS", 1000)
        self.max_value_size = max_value_size or getattr(config, "WORKSPACE_MAX_VALUE_SIZE", 5 * 1024 * 1024)
        self.max_snapshots = max_snapshots or getattr(config, "WORKSPACE_MAX_SNAPSHOTS", 10)
        
        self.acl = acl or WorkspaceACL()
        self._store: Dict[str, WorkspaceEntry] = {}
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._snapshot_history: List[str] = []
        self._global_version = 1
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize workspace store."""
        with self._lock:
            if self._is_initialized:
                return
            self._is_initialized = True
            logger.info("[WorkspaceStore] Shared Workspace Store initialized.")

    def shutdown(self) -> None:
        """Cleanly release workspace store resources."""
        with self._lock:
            self._store.clear()
            self._snapshots.clear()
            self._snapshot_history.clear()
            self._is_initialized = False
            logger.info("[WorkspaceStore] Shared Workspace Store shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return workspace store telemetry health status."""
        with self._lock:
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "total_keys": len(self._store),
                "global_version": self._global_version,
                "snapshot_count": len(self._snapshots),
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply workspace store configuration settings."""
        with self._lock:
            if "max_keys" in config_data:
                self.max_keys = int(config_data["max_keys"])
            if "max_value_size" in config_data:
                self.max_value_size = int(config_data["max_value_size"])
            if "max_snapshots" in config_data:
                self.max_snapshots = int(config_data["max_snapshots"])

    def read(self, key: str, agent_id: str = "system", task_id: Optional[str] = None) -> Optional[Any]:
        """
        Read a value from the workspace store.
        
        Args:
            key (str): Target workspace key.
            agent_id (str): Subagent ID making the read request.
            task_id (Optional[str]): Operational task scope.
            
        Returns:
            Optional[Any]: Key value if found and authorized, else None.
        """
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None

            if not self.acl.validate_access(key, agent_id, PermissionType.READ, task_id, key_owner=entry.owner_agent):
                raise PermissionDeniedException(f"Agent '{agent_id}' denied READ access to workspace key '{key}'.")

            return entry.value

    def get_entry(self, key: str) -> Optional[WorkspaceEntry]:
        """Get the full WorkspaceEntry container object."""
        with self._lock:
            return self._store.get(key)

    def write(self, key: str, value: Any, owner_agent: str = "system", task_id: str = "") -> int:
        """
        Write or update a workspace key value with version increment and quota checks.
        
        Args:
            key (str): Target key.
            value (Any): Payload object.
            owner_agent (str): Subagent performing write.
            task_id (str): Scoped task ID.
            
        Returns:
            int: New key version integer.
        """
        with self._lock:
            # 1. Quota Check: Max Keys Limit
            if key not in self._store and len(self._store) >= self.max_keys:
                raise QuotaExceededException(f"Workspace key quota exceeded (Max {self.max_keys} keys).")

            # 2. Quota Check: Max Value Size Limit
            val_size = sys.getsizeof(value)
            if val_size > self.max_value_size:
                raise QuotaExceededException(f"Workspace value payload size ({val_size} bytes) exceeds max limit ({self.max_value_size} bytes).")

            # 3. ACL Validation
            existing_entry = self._store.get(key)
            owner = existing_entry.owner_agent if existing_entry else owner_agent
            if not self.acl.validate_access(key, owner_agent, PermissionType.WRITE, task_id, key_owner=owner):
                raise PermissionDeniedException(f"Agent '{owner_agent}' denied WRITE access to workspace key '{key}'.")

            is_new = key not in self._store
            now = time.time()

            if is_new:
                entry = WorkspaceEntry(
                    key=key,
                    value=value,
                    version=1,
                    task_id=task_id,
                    owner_agent=owner_agent,
                    created_at=now,
                    updated_at=now,
                )
                self._store[key] = entry
                self._global_version += 1
                event_bus.publish("WORKSPACE_CREATED", key=key, version=1, owner=owner_agent)
            else:
                entry = self._store[key]
                entry.value = value
                entry.version += 1
                entry.updated_at = now
                self._global_version += 1
                event_bus.publish("WORKSPACE_UPDATED", key=key, version=entry.version, owner=owner_agent)

            return entry.version

    def delete(self, key: str, agent_id: str = "system") -> bool:
        """Delete a workspace key."""
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return False

            if not self.acl.validate_access(key, agent_id, PermissionType.WRITE, key_owner=entry.owner_agent):
                raise PermissionDeniedException(f"Agent '{agent_id}' denied DELETE access to key '{key}'.")

            del self._store[key]
            self.acl.revoke_permission(key, agent_id)
            self._global_version += 1
            event_bus.publish("WORKSPACE_DELETED", key=key, deleted_by=agent_id)
            return True

    def exists(self, key: str) -> bool:
        """Check if a workspace key exists."""
        with self._lock:
            return key in self._store

    def create_snapshot(self, created_by: str = "system", description: str = "") -> Dict[str, Any]:
        """
        Create a deep snapshot of the current workspace store state.
        
        Returns:
            Dict[str, Any]: Snapshot metadata container dictionary.
        """
        with self._lock:
            snapshot_id = f"snp_{uuid.uuid4().hex[:12]}"
            now = time.time()

            # Deep copy current workspace entries
            entries_copy = {}
            for k, entry in self._store.items():
                entries_copy[k] = WorkspaceEntry(
                    key=entry.key,
                    value=entry.value,
                    version=entry.version,
                    task_id=entry.task_id,
                    owner_agent=entry.owner_agent,
                    created_at=entry.created_at,
                    updated_at=entry.updated_at,
                )

            snapshot_data = {
                "snapshot_id": snapshot_id,
                "created_at": now,
                "workspace_version": self._global_version,
                "created_by": created_by,
                "description": description,
                "entries": entries_copy,
            }

            self._snapshots[snapshot_id] = snapshot_data
            self._snapshot_history.append(snapshot_id)

            # Enforce snapshot quota limit
            if len(self._snapshot_history) > self.max_snapshots:
                oldest_id = self._snapshot_history.pop(0)
                self._snapshots.pop(oldest_id, None)

            event_bus.publish("SNAPSHOT_CREATED", snapshot_id=snapshot_id, version=self._global_version, creator=created_by)
            logger.info(f"[WorkspaceStore] Created snapshot '{snapshot_id}' (Version {self._global_version}).")
            return snapshot_data

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Restore the workspace store state from a snapshot dictionary.
        
        Args:
            snapshot (Dict[str, Any]): Snapshot data dictionary.
        """
        with self._lock:
            if not snapshot or "entries" not in snapshot:
                return

            self._store.clear()
            snapshot_entries = snapshot["entries"]

            for k, entry in snapshot_entries.items():
                if isinstance(entry, dict):
                    self._store[k] = WorkspaceEntry(
                        key=entry.get("key", k),
                        value=entry.get("value"),
                        version=entry.get("version", 1),
                        task_id=entry.get("task_id", ""),
                        owner_agent=entry.get("owner_agent", "system"),
                        created_at=entry.get("created_at", time.time()),
                        updated_at=entry.get("updated_at", time.time()),
                    )
                elif hasattr(entry, "key"):
                    self._store[k] = WorkspaceEntry(
                        key=entry.key,
                        value=entry.value,
                        version=entry.version,
                        task_id=entry.task_id,
                        owner_agent=entry.owner_agent,
                        created_at=entry.created_at,
                        updated_at=entry.updated_at,
                    )

            if "workspace_version" in snapshot:
                self._global_version = snapshot["workspace_version"]

            event_bus.publish("WORKSPACE_RESTORED", snapshot_id=snapshot.get("snapshot_id", "unknown"), version=self._global_version)
            logger.info(f"[WorkspaceStore] Restored workspace from snapshot '{snapshot.get('snapshot_id')}'.")

    def clear_workspace(self, task_id: Optional[str] = None) -> None:
        """Clear all workspace entries, or scoped to task_id."""
        with self._lock:
            if task_id:
                keys_to_del = [k for k, e in self._store.items() if e.task_id == task_id]
                for k in keys_to_del:
                    del self._store[k]
            else:
                self._store.clear()
            self._global_version += 1
