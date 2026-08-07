"""
ULTRON V3 - Recovery Journal & State Replay Engine
Append-only state log, atomic snapshots, corruption detection, and crash recovery replay.
Zero external framework dependencies.
"""

import hashlib
import json
import os
import threading
import time
from typing import Dict, Any, List, Optional

from core.config import config
from core.event_bus import event_bus
from core.exceptions import JournalCorruptionException, BusException
from core.interfaces import IService
from core.logger import logger


class RecoveryJournal(IService):
    """
    Recovery Journal and Crash State Replay Engine.
    
    Purpose:
    - Provides atomic append-only event logging, state snapshotting, and post-crash state replay.
    
    Responsibilities:
    - Writes line-based journal logs with SHA-256 line integrity hashes.
    - Creates atomic snapshot files (`data/bus_snapshot.json`).
    - Detects journal corruption and safely replays valid state logs on boot.
    - Publishes recovery lifecycle events over Phase 1 EventBus.
    
    Thread-Safety:
    - All journal appends, checkpoints, and recovery replays are guarded by an RLock.
    """

    def __init__(self, journal_path: Optional[str] = None, snapshot_path: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        self.journal_path = os.path.abspath(journal_path or getattr(config, "RECOVERY_JOURNAL_PATH", "data/bus_journal.log"))
        self.snapshot_path = os.path.abspath(snapshot_path or os.path.join(os.path.dirname(self.journal_path), "bus_snapshot.json"))
        
        # Telemetry metrics
        self._recovery_count = 0
        self._last_replay_duration_ms = 0.0
        self._total_replayed_entries = 0
        self._corrupted_lines_count = 0
        
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize recovery journal storage directory."""
        with self._lock:
            if self._is_initialized:
                return
            log_dir = os.path.dirname(self.journal_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            self._is_initialized = True
            logger.info(f"[RecoveryJournal] Initialized at '{self.journal_path}'.")

    def shutdown(self) -> None:
        """Release recovery journal resources."""
        with self._lock:
            self._is_initialized = False
            logger.info("[RecoveryJournal] Cleanly shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return recovery journal health telemetry status."""
        with self._lock:
            journal_size = os.path.getsize(self.journal_path) if os.path.exists(self.journal_path) else 0
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "journal_size_bytes": journal_size,
                "recovery_count": self._recovery_count,
                "corrupted_lines_count": self._corrupted_lines_count,
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration settings."""
        with self._lock:
            if "journal_path" in config_data:
                self.journal_path = os.path.abspath(config_data["journal_path"])

    def append_event(self, action: str, payload: Dict[str, Any]) -> bool:
        """
        Append an event to the append-only journal file with SHA-256 line hash.
        
        Args:
            action (str): Event action keyword.
            payload (Dict[str, Any]): Event data dictionary.
            
        Returns:
            bool: True if appended successfully.
        """
        with self._lock:
            now = time.time()
            data_str = json.dumps({"action": action, "payload": payload, "timestamp": now}, sort_keys=True)
            line_hash = hashlib.sha256(data_str.encode("utf-8")).hexdigest()
            log_entry = f"{line_hash}|{data_str}\n"

            try:
                with open(self.journal_path, "a", encoding="utf-8") as f:
                    f.write(log_entry)
                    f.flush()
                event_bus.publish("JOURNAL_APPENDED", action=action, hash=line_hash[:8])
                return True
            except Exception as ex:
                logger.error(f"[RecoveryJournal] Failed to append event: {ex}")
                return False

    def create_snapshot(self, snapshot_data: Dict[str, Any]) -> str:
        """
        Create an atomic JSON snapshot file.
        
        Args:
            snapshot_data (Dict[str, Any]): Complete state dictionary.
            
        Returns:
            str: Snapshot file path.
        """
        with self._lock:
            tmp_path = f"{self.snapshot_path}.tmp"
            now = time.time()
            snapshot_wrapper = {
                "created_at": now,
                "version": snapshot_data.get("workspace_version", 1),
                "data": snapshot_data,
            }

            def _default_serializer(o: Any) -> Any:
                if hasattr(o, "__dict__"):
                    return o.__dict__
                return str(o)

            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot_wrapper, f, indent=2, default=_default_serializer)
                    f.flush()
                os.replace(tmp_path, self.snapshot_path)
                event_bus.publish("CHECKPOINT_CREATED", snapshot_path=self.snapshot_path, version=snapshot_wrapper["version"])
                logger.info(f"[RecoveryJournal] Atomic snapshot created at '{self.snapshot_path}'.")
                return self.snapshot_path
            except Exception as ex:
                logger.error(f"[RecoveryJournal] Failed to create snapshot: {ex}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise BusException(f"Snapshot creation failed: {ex}")

    def checkpoint(self, snapshot_data: Optional[Dict[str, Any]] = None) -> str:
        """Perform a checkpoint: creates snapshot and truncates journal file."""
        with self._lock:
            snp_path = ""
            if snapshot_data:
                snp_path = self.create_snapshot(snapshot_data)
            self.truncate()
            return snp_path

    def replay(self) -> List[Dict[str, Any]]:
        """
        Read and replay journal entries, verifying SHA-256 line hashes.
        
        Returns:
            List[Dict[str, Any]]: List of valid event entries replayed.
        """
        replayed: List[Dict[str, Any]] = []
        if not os.path.exists(self.journal_path):
            return replayed

        with self._lock:
            start_t = time.time()
            with open(self.journal_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split("|", 1)
                    if len(parts) != 2:
                        self._corrupted_lines_count += 1
                        logger.warning(f"[RecoveryJournal] Corrupted line {line_num} format.")
                        continue

                    expected_hash, data_str = parts
                    actual_hash = hashlib.sha256(data_str.encode("utf-8")).hexdigest()

                    if expected_hash != actual_hash:
                        self._corrupted_lines_count += 1
                        logger.error(f"[RecoveryJournal] SHA-256 hash mismatch on line {line_num}.")
                        continue

                    try:
                        entry = json.loads(data_str)
                        replayed.append(entry)
                    except Exception:
                        self._corrupted_lines_count += 1

            self._last_replay_duration_ms = (time.time() - start_t) * 1000.0
            self._total_replayed_entries += len(replayed)
            return replayed

    def recover(self, workspace_store: Optional[Any] = None) -> bool:
        """
        Execute crash recovery protocol: loads snapshot if present and replays log entries.
        
        Args:
            workspace_store (Optional[Any]): Target workspace store to apply replayed state.
            
        Returns:
            bool: True if recovery completed cleanly.
        """
        with self._lock:
            self._recovery_count += 1
            event_bus.publish("RECOVERY_STARTED", count=self._recovery_count)
            logger.info(f"[RecoveryJournal] Starting recovery process #{self._recovery_count}...")

            # 1. Load Snapshot if present
            snapshot_data = self.load_snapshot()
            if snapshot_data and workspace_store:
                workspace_store.restore_snapshot(snapshot_data.get("data", {}))

            # 2. Replay Journal Entries
            replayed_entries = self.replay()
            if workspace_store:
                for event in replayed_entries:
                    act = event.get("action")
                    pld = event.get("payload", {})
                    if act == "WRITE":
                        workspace_store.write(pld.get("key"), pld.get("value"), owner_agent=pld.get("owner", "system"))
                    elif act == "DELETE":
                        workspace_store.delete(pld.get("key"))

            event_bus.publish("RECOVERY_COMPLETED", count=self._recovery_count, replayed=len(replayed_entries))
            logger.info(f"[RecoveryJournal] Recovery #{self._recovery_count} completed ({len(replayed_entries)} entries replayed).")
            return True

    def load_snapshot(self) -> Optional[Dict[str, Any]]:
        """Load atomic state snapshot if present on disk."""
        with self._lock:
            if not os.path.exists(self.snapshot_path):
                return None
            try:
                with open(self.snapshot_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as ex:
                logger.error(f"[RecoveryJournal] Failed to load snapshot: {ex}")
                raise JournalCorruptionException(f"Corrupted snapshot file: {ex}")

    def truncate(self) -> bool:
        """Truncate the journal file."""
        with self._lock:
            try:
                with open(self.journal_path, "w", encoding="utf-8") as f:
                    f.truncate(0)
                logger.info("[RecoveryJournal] Journal file truncated.")
                return True
            except Exception as ex:
                logger.error(f"[RecoveryJournal] Failed to truncate journal: {ex}")
                return False
                logger.info("[RecoveryJournal] Journal file truncated.")
                return True
            except Exception as ex:
                logger.error(f"[RecoveryJournal] Failed to truncate journal: {ex}")
                return False

    def get_replay_metrics(self) -> Dict[str, Any]:
        """Return replay and recovery metrics."""
        with self._lock:
            return {
                "recovery_count": self._recovery_count,
                "last_replay_duration_ms": round(self._last_replay_duration_ms, 2),
                "total_replayed_entries": self._total_replayed_entries,
                "corrupted_lines_count": self._corrupted_lines_count,
            }
