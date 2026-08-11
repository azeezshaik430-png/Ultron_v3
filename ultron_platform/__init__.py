"""
ULTRON V3 - Platform Abstraction Layer
OS detection and adapter factory.

Package name: ultron_platform
(Named with 'ultron_' prefix to avoid shadowing Python's stdlib 'platform' module.)

Usage:
    from ultron_platform import get_platform_adapter
    adapter = get_platform_adapter()
    adapter.open_path("/some/path")
"""

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ultron_platform.interface import PlatformAdapter

_adapter_instance = None


def get_platform_adapter() -> "PlatformAdapter":
    """
    Return the singleton platform adapter for the current OS.

    Returns:
        WindowsAdapter on Windows (sys.platform == 'win32')
        LinuxAdapter on Linux (sys.platform.startswith('linux'))
    """
    global _adapter_instance
    if _adapter_instance is not None:
        return _adapter_instance

    if sys.platform == "win32":
        from ultron_platform.windows_adapter import WindowsAdapter
        _adapter_instance = WindowsAdapter()
    elif sys.platform.startswith("linux"):
        from ultron_platform.linux_adapter import LinuxAdapter
        _adapter_instance = LinuxAdapter()
    elif sys.platform == "darwin":
        from ultron_platform.macos_adapter import MacOSAdapter
        _adapter_instance = MacOSAdapter()
    else:
        from ultron_platform.linux_adapter import LinuxAdapter
        _adapter_instance = LinuxAdapter()

    return _adapter_instance


def is_windows() -> bool:
    """Return True if the current OS is Windows."""
    return sys.platform == "win32"


def is_linux() -> bool:
    """Return True if the current OS is Linux."""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """Return True if the current OS is macOS."""
    return sys.platform == "darwin"


def platform_name() -> str:
    """Return a human-readable platform name string."""
    if sys.platform == "win32":
        return "Windows"
    if sys.platform.startswith("linux"):
        return "Linux"
    if sys.platform == "darwin":
        return "macOS"
    return sys.platform
