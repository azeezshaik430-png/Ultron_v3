"""
ULTRON V3 - Platform Adapter Interface
Abstract base class defining the platform abstraction contract.

All platform adapters (Windows, Linux) must implement every method here.
The core business logic must only call methods on this interface — never
directly invoke OS-specific APIs.

Capability model:
    Each method that may be unavailable on certain platforms returns a dict:
        {"available": False, "reason": "..."}  → capability not present
        {"available": True, "result": ...}     → success
    or raises an explicit PlatformCapabilityError.

This design ensures the core assistant never silently fails on unsupported
platforms — it receives an honest status and can respond accordingly.
"""

from enum import Enum
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CapabilityStatus(str, Enum):
    """
    Standardized capability support status for cross-platform operations.
    """
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    REQUIRES_PERMISSION = "REQUIRES_PERMISSION"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class PlatformCapabilityError(Exception):
    """
    Raised when a platform adapter is asked to perform an operation
    that does not exist on the current OS and has no safe fallback.
    """
    pass


class PlatformAdapter(ABC):
    """
    Abstract platform adapter contract.
    Concrete implementations: WindowsAdapter, LinuxAdapter, MacOSAdapter.
    """

    # =========================================================================
    # IDENTITY & CAPABILITIES
    # =========================================================================

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform name, e.g. 'Windows', 'Linux', 'macOS'."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, CapabilityStatus]:
        """
        Return a map of all OS capability names to their CapabilityStatus on the current host.
        """
        pass

    @abstractmethod
    def get_capability_status(self, capability: str) -> CapabilityStatus:
        """
        Return the CapabilityStatus for a specific capability name.
        """
        pass

    # =========================================================================
    # APPLICATION LAUNCHING
    # =========================================================================

    @abstractmethod
    def open_application(self, path: str) -> Dict[str, Any]:
        """
        Launch an application at the given absolute path.

        Args:
            path: Absolute path to the executable.

        Returns:
            {"available": True, "result": "Opening <name>."} on success.
            {"available": False, "reason": "..."} if not applicable.
        """
        pass

    @abstractmethod
    def get_executable_extension(self) -> str:
        """
        Return the platform-appropriate executable file extension.

        Returns:
            ".exe" on Windows, "" on Linux.
        """
        pass

    @abstractmethod
    def get_app_search_locations(self) -> List[str]:
        """
        Return a list of filesystem locations to scan for installed applications.

        Returns:
            List of absolute directory paths appropriate for the current OS.
        """
        pass

    @abstractmethod
    def get_user_appdata_path(self) -> str:
        """
        Return the user-level application data directory.

        Windows: %LOCALAPPDATA%  (e.g. C:\\Users\\<user>\\AppData\\Local)
        Linux:   ~/.local/share
        """
        pass

    # =========================================================================
    # WINDOW MANAGEMENT
    # =========================================================================

    @abstractmethod
    def focus_window(self, app_name: str) -> Dict[str, Any]:
        """
        Bring the window matching app_name to the foreground.

        Args:
            app_name: Case-insensitive partial match against window titles.

        Returns:
            {"available": True, "result": True/False} on success/no match.
            {"available": False, "reason": "..."} if window management unavailable.
        """
        pass

    # =========================================================================
    # FILE MANAGER / PATH OPENING
    # =========================================================================

    @abstractmethod
    def open_path(self, path: str) -> Dict[str, Any]:
        """
        Open a file or directory in the native file manager or default application.

        Windows: explorer <path>  /  os.startfile(path)
        Linux:   xdg-open <path>

        Args:
            path: Absolute path to file or directory.

        Returns:
            {"available": True, "result": "Opening <path>."} on success.
            {"available": False, "reason": "..."} if unavailable.
        """
        pass

    @abstractmethod
    def get_search_locations(self) -> List[str]:
        """
        Return a list of common user directories to search for files.

        Windows: Desktop, Documents, Downloads, C:\\, D:\\  (if present)
        Linux:   ~/Desktop, ~/Documents, ~/Downloads, /home/<user>
        """
        pass

    @abstractmethod
    def get_common_dirs(self) -> Dict[str, Optional[str]]:
        """
        Return a dict of common named directories.

        Keys: "downloads", "desktop", "documents", "home"
        Values: Absolute paths, or None if the directory does not exist.
        """
        pass

    # =========================================================================
    # VOLUME / AUDIO CONTROL
    # =========================================================================

    @abstractmethod
    def volume_up(self, step: float = 0.1) -> Dict[str, Any]:
        """Increase master volume by step (0.0–1.0 scale)."""
        pass

    @abstractmethod
    def volume_down(self, step: float = 0.1) -> Dict[str, Any]:
        """Decrease master volume by step."""
        pass

    @abstractmethod
    def mute(self) -> Dict[str, Any]:
        """Mute master audio output."""
        pass

    @abstractmethod
    def unmute(self) -> Dict[str, Any]:
        """Unmute master audio output."""
        pass

    @abstractmethod
    def set_volume(self, level: float) -> Dict[str, Any]:
        """
        Set master volume to a specific level.

        Args:
            level: Float 0.0 (silent) to 1.0 (maximum).
        """
        pass

    # =========================================================================
    # SYSTEM POWER / SESSION CONTROL
    # =========================================================================

    @abstractmethod
    def shutdown(self, delay_sec: int = 5) -> Dict[str, Any]:
        """
        Initiate OS shutdown sequence.

        IMPORTANT: Callers MUST perform the security token check BEFORE calling this.
        The adapter executes the OS command without re-validating the token.

        Args:
            delay_sec: Delay in seconds before shutdown.
        """
        pass

    @abstractmethod
    def restart(self, delay_sec: int = 5) -> Dict[str, Any]:
        """Initiate OS restart sequence."""
        pass

    @abstractmethod
    def sleep(self) -> Dict[str, Any]:
        """Suspend the system to RAM (sleep mode)."""
        pass

    @abstractmethod
    def lock(self) -> Dict[str, Any]:
        """Lock the current user session."""
        pass

    @abstractmethod
    def sign_out(self) -> Dict[str, Any]:
        """Sign out / log off the current user session."""
        pass

    @abstractmethod
    def open_settings(self) -> Dict[str, Any]:
        """Open the OS system settings panel."""
        pass

    # =========================================================================
    # SHELL / TERMINAL
    # =========================================================================

    @abstractmethod
    def get_terminal_command(self) -> List[str]:
        """
        Return the command list to launch a terminal emulator.

        Windows: ["cmd.exe"]  or  ["powershell.exe"]
        Linux:   ["xterm"]    or  ["gnome-terminal"]  or best available
        macOS:   ["open", "-a", "Terminal"]
        """
        pass

    # =========================================================================
    # EXTENDED HARDWARE & OS CONTROLS
    # =========================================================================

    @abstractmethod
    def set_brightness(self, level: float) -> Dict[str, Any]:
        """Set display brightness level (0.0 to 1.0)."""
        pass

    @abstractmethod
    def get_brightness(self) -> Dict[str, Any]:
        """Get current display brightness level (0.0 to 1.0)."""
        pass

    @abstractmethod
    def get_wifi_status(self) -> Dict[str, Any]:
        """Get Wi-Fi interface status and connected network SSID."""
        pass

    @abstractmethod
    def get_bluetooth_status(self) -> Dict[str, Any]:
        """Get Bluetooth interface state."""
        pass

    @abstractmethod
    def get_clipboard(self) -> Dict[str, Any]:
        """Read text from OS system clipboard."""
        pass

    @abstractmethod
    def set_clipboard(self, text: str) -> Dict[str, Any]:
        """Copy text to OS system clipboard."""
        pass

    @abstractmethod
    def send_notification(self, title: str, message: str) -> Dict[str, Any]:
        """Send a native OS desktop notification."""
        pass

    @abstractmethod
    def take_screenshot(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Capture screen image to file."""
        pass

    @abstractmethod
    def mouse_click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        """Simulate mouse click at screen coordinates (x, y)."""
        pass

    @abstractmethod
    def keyboard_type(self, text: str) -> Dict[str, Any]:
        """Simulate keyboard typing of text string."""
        pass
