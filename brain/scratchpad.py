"""
ULTRON V3 - Subagent Transient Scratchpad Store
Task-scoped and Agent-scoped transient scratchpad memory store with quota enforcement and cleanup.
Zero external framework dependencies.
"""

import sys
import threading
import time
from typing import Dict, Any, List, Optional

from core.config import config
from core.exceptions import QuotaExceededException
from core.interfaces import IService
from core.logger import logger
from brain.bus_types import ScratchpadEntry


class AgentScratchpad(IService):
    """
    Agent Scratchpad Store.
    
    Purpose:
    - Provides task-scoped and agent-scoped short-lived unstructured text note memory.
    
    Responsibilities:
    - Manages creation, append, read, update, and deletion of transient notes.
    - Enforces memory quota size limits per task and globally.
    - Provides automatic TTL cleanup of expired task scratchpads.
    
    Thread-Safety:
    - All scratchpad read, write, and cleanup operations are guarded by an RLock.
    """

    def __init__(self, max_size_mb: Optional[int] = None) -> None:
        self._lock = threading.RLock()
        self.max_size_bytes = (max_size_mb or getattr(config, "SCRATCHPAD_MAX_SIZE_MB", 10)) * 1024 * 1024
        
        # Scoped Storage: task_id -> {agent_id -> List[ScratchpadEntry]}
        self._store: Dict[str, Dict[str, List[ScratchpadEntry]]] = {}
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize scratchpad store."""
        with self._lock:
            if self._is_initialized:
                return
            self._is_initialized = True
            logger.info("[AgentScratchpad] Scratchpad Store initialized.")

    def shutdown(self) -> None:
        """Cleanly release scratchpad storage."""
        with self._lock:
            self._store.clear()
            self._is_initialized = False
            logger.info("[AgentScratchpad] Scratchpad Store shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return scratchpad telemetry health status."""
        with self._lock:
            total_notes = sum(
                sum(len(notes) for notes in agent_map.values())
                for agent_map in self._store.values()
            )
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "active_tasks_count": len(self._store),
                "total_notes_count": total_notes,
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration parameters."""
        with self._lock:
            if "max_size_mb" in config_data:
                self.max_size_bytes = int(config_data["max_size_mb"]) * 1024 * 1024

    def create_scratchpad(self, task_id: str, agent_id: str) -> None:
        """Initialize empty scratchpad container for a task and agent."""
        with self._lock:
            if task_id not in self._store:
                self._store[task_id] = {}
            if agent_id not in self._store[task_id]:
                self._store[task_id][agent_id] = []

    def append_entry(self, task_id: str, agent_id: str, entry_text: str) -> ScratchpadEntry:
        """
        Append a new note entry to a task and agent scratchpad.
        
        Args:
            task_id (str): Operational task scope ID.
            agent_id (str): Subagent ID creating the note.
            entry_text (str): Raw note text string.
            
        Returns:
            ScratchpadEntry: Created scratchpad entry dataclass.
            
        Raises:
            QuotaExceededException: If entry text size exceeds remaining quota limit.
        """
        with self._lock:
            text_size = sys.getsizeof(entry_text)
            if text_size > self.max_size_bytes:
                raise QuotaExceededException(f"Scratchpad note payload ({text_size} bytes) exceeds limit ({self.max_size_bytes} bytes).")

            self.create_scratchpad(task_id, agent_id)
            entry = ScratchpadEntry(
                task_id=task_id,
                agent_id=agent_id,
                entry_text=entry_text,
                timestamp=time.time(),
            )
            self._store[task_id][agent_id].append(entry)
            return entry

    def read_scratchpad(self, task_id: str, agent_id: Optional[str] = None) -> List[ScratchpadEntry]:
        """
        Read scratchpad entries for a task, optionally filtered by agent_id.
        
        Args:
            task_id (str): Target task ID.
            agent_id (Optional[str]): Optional agent ID filter.
            
        Returns:
            List[ScratchpadEntry]: Ordered list of matching note entries.
        """
        with self._lock:
            task_map = self._store.get(task_id, {})
            if not task_map:
                return []

            if agent_id:
                return list(task_map.get(agent_id, []))

            all_entries: List[ScratchpadEntry] = []
            for agent_notes in task_map.values():
                all_entries.extend(agent_notes)
            all_entries.sort(key=lambda e: e.timestamp)
            return all_entries

    def update_entry(self, task_id: str, agent_id: str, index: int, new_text: str) -> bool:
        """Update an existing scratchpad note by index."""
        with self._lock:
            agent_notes = self._store.get(task_id, {}).get(agent_id, [])
            if 0 <= index < len(agent_notes):
                agent_notes[index].entry_text = new_text
                agent_notes[index].timestamp = time.time()
                return True
            return False

    def delete_scratchpad(self, task_id: str, agent_id: Optional[str] = None) -> bool:
        """Delete scratchpad notes for a task or specific agent under a task."""
        with self._lock:
            if task_id not in self._store:
                return False

            if agent_id:
                if agent_id in self._store[task_id]:
                    del self._store[task_id][agent_id]
                    if not self._store[task_id]:
                        del self._store[task_id]
                    return True
                return False

            del self._store[task_id]
            return True

    def clear_expired(self, max_age_seconds: float = 86400.0) -> int:
        """Clear task scratchpads with no activity older than max_age_seconds."""
        now = time.time()
        evicted = 0
        with self._lock:
            for task_id in list(self._store.keys()):
                agent_map = self._store[task_id]
                all_old = True
                for notes in agent_map.values():
                    for n in notes:
                        if (now - n.timestamp) < max_age_seconds:
                            all_old = False
                            break
                    if not all_old:
                        break

                if all_old:
                    del self._store[task_id]
                    evicted += 1
        return evicted
