"""
ULTRON V3 - Workspace Access Control Layer (ACL)
Fine-grained access control list evaluator for shared workspace keys.
Zero external framework dependencies.
"""

import threading
from enum import Enum
from typing import Dict, Any, Optional, Set
from core.exceptions import PermissionDeniedException


class PermissionType(str, Enum):
    """Workspace key permission types."""
    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"


class AccessTier(str, Enum):
    """Workspace key access tiers."""
    OWNER = "OWNER"
    SHARED = "SHARED"
    READ_ONLY = "READ_ONLY"
    TEMPORARY = "TEMPORARY"


class WorkspaceACL:
    """
    Workspace Access Control Layer.
    
    Purpose:
    - Evaluates subagent permissions for shared workspace key access.
    
    Responsibilities:
    - Grants and revokes key-level permissions.
    - Validates READ, WRITE, and EXECUTE requests for Agent-scoped and Task-scoped access.
    
    Thread-Safety:
    - All ACL evaluations and mutations are guarded by an RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Mapping: key -> {agent_id -> (access_tier, task_id)}
        self._permissions: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def grant_permission(
        self,
        key: str,
        agent_id: str,
        access_tier: AccessTier,
        task_id: Optional[str] = None,
    ) -> None:
        """
        Grant a subagent permission access tier on a workspace key.
        
        Args:
            key (str): Target workspace key.
            agent_id (str): Target subagent ID.
            access_tier (AccessTier): Permission access tier.
            task_id (Optional[str]): Optional task scoping ID.
        """
        with self._lock:
            if key not in self._permissions:
                self._permissions[key] = {}
            self._permissions[key][agent_id] = {
                "access_tier": access_tier,
                "task_id": task_id,
            }

    def revoke_permission(self, key: str, agent_id: str) -> None:
        """Revoke subagent permissions on a key."""
        with self._lock:
            if key in self._permissions and agent_id in self._permissions[key]:
                del self._permissions[key][agent_id]
                if not self._permissions[key]:
                    del self._permissions[key]

    def validate_access(
        self,
        key: str,
        agent_id: str,
        perm_type: PermissionType,
        task_id: Optional[str] = None,
        key_owner: str = "system",
    ) -> bool:
        """
        Validate whether an agent has permission to perform an operation on a key.
        
        Args:
            key (str): Target workspace key.
            agent_id (str): Subagent ID performing the operation.
            perm_type (PermissionType): Operation permission requested (READ, WRITE, EXECUTE).
            task_id (Optional[str]): Operational task scope.
            key_owner (str): Owner agent of the key.
            
        Returns:
            bool: True if authorized, False otherwise.
        """
        with self._lock:
            # System and key owners always have full access
            if agent_id in ["system", key_owner]:
                return True

            key_perms = self._permissions.get(key, {})
            agent_perm = key_perms.get(agent_id)

            if not agent_perm:
                # Default policy: open for system/unrestricted keys unless explicit tier set
                if not key_perms:
                    return True
                return False

            tier: AccessTier = agent_perm["access_tier"]
            scoped_task = agent_perm.get("task_id")

            # Check task scoping restriction if configured
            if scoped_task and task_id and scoped_task != task_id:
                return False

            if tier in [AccessTier.OWNER, AccessTier.SHARED]:
                return True

            if tier in [AccessTier.READ_ONLY, AccessTier.TEMPORARY]:
                if perm_type == PermissionType.READ:
                    return True
                return False

            return False

    def clear(self) -> None:
        """Clear all ACL rules."""
        with self._lock:
            self._permissions.clear()
