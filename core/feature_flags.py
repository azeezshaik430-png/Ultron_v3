"""
ULTRON V3 - Runtime Feature Flag Manager
Thread-safe runtime feature flag manager with default flags and query controls.
Zero external framework dependencies.
"""

import threading
from typing import Dict, Any


class FeatureFlagManager:
    """
    Runtime Feature Flag Manager.
    
    Purpose:
    - Centralized control of runtime component execution toggles.
    
    Responsibilities:
    - Manages boolean feature flags allowing dynamic component enable/disable.
    - Provides safe default flag initialization.
    
    Thread-Safety:
    - All flag state mutations and reads are protected by an RLock.
    """

    DEFAULT_FLAGS: Dict[str, bool] = {
        "ENABLE_AGENT_BUS": True,
        "ENABLE_ROUTER": True,
        "ENABLE_GC": True,
        "ENABLE_METRICS": True,
        "ENABLE_JOURNAL": True,
        "ENABLE_RECOVERY": True,
        "ENABLE_ACL": True,
        "ENABLE_SCRATCHPAD": True,
        "ENABLE_ARTIFACTS": True,
        "ENABLE_HEALTH_MONITOR": True,
    }

    def __init__(self, initial_flags: Dict[str, bool] = None) -> None:
        self._lock = threading.RLock()
        self._flags: Dict[str, bool] = dict(self.DEFAULT_FLAGS)
        if initial_flags:
            self._flags.update(initial_flags)

    def is_enabled(self, flag_name: str) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag_name (str): Target feature flag name.
            
        Returns:
            bool: True if enabled, False otherwise (defaults to False if un-registered).
        """
        with self._lock:
            return self._flags.get(flag_name, False)

    def enable_flag(self, flag_name: str) -> None:
        """
        Enable a feature flag at runtime.
        
        Args:
            flag_name (str): Target feature flag name.
        """
        with self._lock:
            self._flags[flag_name] = True

    def disable_flag(self, flag_name: str) -> None:
        """
        Disable a feature flag at runtime.
        
        Args:
            flag_name (str): Target feature flag name.
        """
        with self._lock:
            self._flags[flag_name] = False

    def get_all_flags(self) -> Dict[str, bool]:
        """
        Return a copy of all current feature flags and their states.
        
        Returns:
            Dict[str, bool]: Feature flag mapping dictionary.
        """
        with self._lock:
            return dict(self._flags)

    def reset_defaults(self) -> None:
        """Reset feature flags to default baseline."""
        with self._lock:
            self._flags = dict(self.DEFAULT_FLAGS)
