"""
ULTRON V3 - Thread-Safe Session Manager
Manages system state, authentication, modes, and running tasks.
Authentication lives strictly in memory for the current application session.
Protected by threading.RLock for thread safety.
"""

import threading
import time
import uuid
from typing import Optional, Dict, Any


class SessionManager:
    """Thread-safe central session manager tracking ULTRON execution context."""

    def __init__(self) -> None:
        self._lock: threading.RLock = threading.RLock()
        self.is_authenticated: bool = False
        self.is_active_mode: bool = True
        self.is_sleeping: bool = False
        self.current_user: str = "Boss"
        self.current_task: Optional[str] = None
        self.current_agent: Optional[str] = None
        self.session_data: Dict[str, Any] = {}
        self.pending_confirmation: Optional[Dict[str, Any]] = None

    def set_auth(self, status: bool) -> None:
        """Set voice authentication state in memory (Thread-safe)."""
        with self._lock:
            self.is_authenticated = status

    def enter_sleep(self) -> None:
        """Toggle to sleep mode without clearing authentication (Thread-safe)."""
        with self._lock:
            self.is_sleeping = True
            self.is_active_mode = False

    def enter_active(self) -> None:
        """Toggle to active mode (Thread-safe)."""
        with self._lock:
            self.is_sleeping = False
            self.is_active_mode = True

    def exit_sleep(self) -> None:
        """Exit sleep mode into active mode (Thread-safe)."""
        self.enter_active()

    def set_pending_confirmation(
        self,
        action: str,
        command: str,
        payload: Any = None,
        requires_double: bool = False,
        action_phrase: str = "CONFIRM",
        exec_func: Any = None,
        timeout_seconds: float = 15.0
    ) -> Dict[str, Any]:
        """Create a new pending token-based confirmation object in memory only."""
        with self._lock:
            conf_id = uuid.uuid4().hex
            now = time.time()
            data = {
                "id": conf_id,
                "confirmation_id": conf_id[:8],
                "action": action,
                "command": command,
                "payload": payload,
                "step": 1,
                "created_at": now,
                "expires_at": now + timeout_seconds,
                "validated": False,
                "confirmed": False,
                "requires_double": requires_double,
                "action_phrase": action_phrase,
                "exec_func": exec_func,
            }
            self.pending_confirmation = data
            return data

    def clear_pending_confirmation(self) -> None:
        """Completely destroy active pending confirmation token (In-Memory Only)."""
        with self._lock:
            self.pending_confirmation = None

    def is_confirmation_expired(self, timeout_seconds: float = 15.0) -> bool:
        """Check if active token-based confirmation has exceeded expiration time (In-Memory Only)."""
        with self._lock:
            if not self.pending_confirmation:
                return False
            now = time.time()
            expires_at = self.pending_confirmation.get("expires_at")
            created_at = self.pending_confirmation.get("created_at", 0)
            if expires_at and now > expires_at:
                return True
            if created_at and (now - created_at) > timeout_seconds:
                return True
            return False

    def save(self) -> None:
        """Save session persistent state to disk, EXCLUDING authentication and confirmation state (Thread-safe)."""
        with self._lock:
            import json, os
            os.makedirs("data", exist_ok=True)
            session_file = os.path.join("data", "session.json")
            # Strictly persist non-sensitive execution metrics
            persistent_state = {
                "active_mode": self.is_active_mode,
                "sleeping": self.is_sleeping,
                "current_user": self.current_user,
                "current_task": self.current_task,
                "current_agent": self.current_agent,
            }
            try:
                with open(session_file, "w", encoding="utf-8") as f:
                    json.dump(persistent_state, f, indent=2)
            except Exception:
                pass

    def reset(self) -> None:
        """Reset session authentication and confirmation state (Thread-safe)."""
        with self._lock:
            self.is_authenticated = False
            self.is_sleeping = False
            self.is_active_mode = False
            self.current_task = None
            self.current_agent = None
            self.pending_confirmation = None
            self.session_data.clear()

    def set_current_task(self, task_name: Optional[str]) -> None:
        """Update current executing task (Thread-safe)."""
        with self._lock:
            self.current_task = task_name

    def set_current_agent(self, agent_name: Optional[str]) -> None:
        """Update current active agent (Thread-safe)."""
        with self._lock:
            self.current_agent = agent_name

    def get_state(self) -> Dict[str, Any]:
        """Return current session state dictionary (Thread-safe)."""
        with self._lock:
            return {
                "authenticated": False,  # Never expose auth status in exported state
                "active_mode": self.is_active_mode,
                "sleeping": self.is_sleeping,
                "current_user": self.current_user,
                "current_task": self.current_task,
                "current_agent": self.current_agent,
            }


# Global Session Singleton
session = SessionManager()
