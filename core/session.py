"""
ULTRON V3 - Thread-Safe Session Manager
Manages system state, authentication, modes, and running tasks.
Authentication lives strictly in memory for the current application session.
Protected by threading.RLock for thread safety.
"""

import threading
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

    def reset(self) -> None:
        """Reset session authentication and state (Thread-safe)."""
        with self._lock:
            self.is_authenticated = False
            self.is_sleeping = False
            self.is_active_mode = False
            self.current_task = None
            self.current_agent = None
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
                "authenticated": self.is_authenticated,
                "active_mode": self.is_active_mode,
                "sleeping": self.is_sleeping,
                "current_user": self.current_user,
                "current_task": self.current_task,
                "current_agent": self.current_agent,
            }


# Global Session Singleton
session = SessionManager()
