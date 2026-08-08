"""
ULTRON V3
File Manager

Cross-platform: uses platform adapter for opening paths and for
OS-specific file browser commands. Windows drive-specific functions
(C drive, D drive) are preserved but route through the adapter so
they degrade gracefully on Linux.
"""

import os
import ultron_platform


def _adapter():
    return ultron_platform.get_platform_adapter()


def _open(path: str, label: str) -> str:
    """Open a path and return a user-friendly result string."""
    result = _adapter().open_path(path)
    if result.get("available"):
        return f"Opening {label}."
    reason = result.get("reason", "File manager unavailable.")
    return f"Cannot open {label}: {reason}"


def open_downloads():
    path = os.path.join(os.path.expanduser("~"), "Downloads")
    return _open(path, "Downloads")


def open_desktop():
    path = os.path.join(os.path.expanduser("~"), "Desktop")
    return _open(path, "Desktop")


def open_documents():
    path = os.path.join(os.path.expanduser("~"), "Documents")
    return _open(path, "Documents")


def open_d_drive():
    """
    Open D: drive on Windows.
    On Linux, returns an appropriate unavailability message.
    """
    if ultron_platform.is_windows():
        d_path = "D:\\"
        if os.path.isdir(d_path):
            return _open(d_path, "D drive")
        return "D drive is not available on this system."
    return "D drive is a Windows-specific concept and is not available on this platform."


def open_c_drive():
    """
    Open C: drive on Windows.
    On Linux, opens the home directory instead.
    """
    if ultron_platform.is_windows():
        return _open("C:\\", "C drive")
    return _open(os.path.expanduser("~"), "home directory")