"""
ULTRON V3 - Windows Platform Adapter
Wraps all existing Windows-specific skill implementations behind the
PlatformAdapter interface. This preserves 100% of existing Windows
functionality while providing a clean adapter surface.

All Windows capabilities are imported lazily so that this file can be
imported safely on Linux for inspection — actual Windows COM/Win32 calls
only execute at runtime when the methods are called.
"""

import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from ultron_platform.interface import PlatformAdapter, PlatformCapabilityError


class WindowsAdapter(PlatformAdapter):
    """
    Windows platform adapter.

    Wraps:
        - pycaw  (COM audio endpoint)
        - pygetwindow (window management)
        - os.startfile (file/app launch)
        - Windows shutdown / rundll32 / explorer / powershell
    """

    @property
    def platform_name(self) -> str:
        return "Windows"

    # =========================================================================
    # APPLICATION LAUNCHING
    # =========================================================================

    def open_application(self, path: str) -> Dict[str, Any]:
        """Launch an application by absolute path using os.startfile."""
        if not os.path.exists(path):
            return {"available": True, "result": None, "error": f"Path not found: {path}"}
        try:
            os.startfile(path)  # noqa: S606 — Windows-only, intentional
            name = os.path.basename(path)
            return {"available": True, "result": f"Opening {name}"}
        except Exception as exc:
            return {"available": True, "result": None, "error": str(exc)}

    def get_executable_extension(self) -> str:
        return ".exe"

    def get_app_search_locations(self) -> List[str]:
        """
        Return standard Windows application install directories.
        Uses environment variables where available to avoid machine-specific paths.
        """
        locations = []
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_appdata = os.environ.get("LOCALAPPDATA", "")

        locations.append(program_files)
        locations.append(program_files_x86)
        if local_appdata:
            locations.append(local_appdata)

        return [loc for loc in locations if os.path.isdir(loc)]

    def get_user_appdata_path(self) -> str:
        """Return %LOCALAPPDATA% or fallback to user home AppData/Local."""
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata and os.path.isdir(local_appdata):
            return local_appdata
        return os.path.join(os.path.expanduser("~"), "AppData", "Local")

    # =========================================================================
    # WINDOW MANAGEMENT
    # =========================================================================

    def focus_window(self, app_name: str) -> Dict[str, Any]:
        """Bring a named window to foreground using pygetwindow."""
        try:
            import pygetwindow as gw  # Windows-only

            app_name_lower = app_name.lower()
            windows = gw.getAllWindows()
            for window in windows:
                if window.title and app_name_lower in window.title.lower():
                    if window.isMinimized:
                        window.restore()
                    window.activate()
                    return {"available": True, "result": True}
            return {"available": True, "result": False}
        except ImportError:
            return {"available": False, "reason": "pygetwindow not installed"}
        except Exception as exc:
            return {"available": True, "result": False, "error": str(exc)}

    # =========================================================================
    # FILE MANAGER / PATH OPENING
    # =========================================================================

    def open_path(self, path: str) -> Dict[str, Any]:
        """
        Open a path using Windows Explorer for directories, or os.startfile for files.
        """
        try:
            if os.path.isdir(path):
                subprocess.Popen(["explorer", path])
            elif os.path.isfile(path):
                os.startfile(path)  # noqa: S606
            else:
                # Attempt open regardless (e.g. virtual drive roots like C:\)
                subprocess.Popen(["explorer", path])
            return {"available": True, "result": f"Opening {path}"}
        except Exception as exc:
            return {"available": True, "result": None, "error": str(exc)}

    def get_search_locations(self) -> List[str]:
        """
        Return Windows user directories plus physical drive roots that exist.
        Replaces the previous hardcoded C:\\ and D:\\ literals.
        """
        locations = [
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Downloads"),
        ]
        # Add all mounted Windows drive root paths that actually exist
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.isdir(drive):
                locations.append(drive)
        return [loc for loc in locations if os.path.exists(loc)]

    def get_common_dirs(self) -> Dict[str, Optional[str]]:
        """Return common Windows user directories."""
        dirs = {
            "home": os.path.expanduser("~"),
            "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
            "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
            "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        }
        return {k: v if os.path.exists(v) else None for k, v in dirs.items()}

    # =========================================================================
    # VOLUME / AUDIO CONTROL
    # =========================================================================

    def _get_volume_interface(self) -> Any:
        """Return a pycaw IAudioEndpointVolume COM interface."""
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        from ctypes import POINTER, cast
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return volume

    def volume_up(self, step: float = 0.1) -> Dict[str, Any]:
        try:
            vol = self._get_volume_interface()
            current = vol.GetMasterVolumeLevelScalar()
            vol.SetMasterVolumeLevelScalar(min(current + step, 1.0), None)
            return {"available": True, "result": "Volume increased Boss."}
        except Exception as exc:
            return {"available": True, "result": None, "error": str(exc)}

    def volume_down(self, step: float = 0.1) -> Dict[str, Any]:
        try:
            vol = self._get_volume_interface()
            current = vol.GetMasterVolumeLevelScalar()
            vol.SetMasterVolumeLevelScalar(max(current - step, 0.0), None)
            return {"available": True, "result": "Volume decreased Boss."}
        except Exception as exc:
            return {"available": True, "result": None, "error": str(exc)}

    def mute(self) -> Dict[str, Any]:
        try:
            vol = self._get_volume_interface()
            vol.SetMute(1, None)
            return {"available": True, "result": "Volume muted Boss."}
        except Exception as exc:
            return {"available": True, "result": None, "error": str(exc)}

    def unmute(self) -> Dict[str, Any]:
        try:
            vol = self._get_volume_interface()
            vol.SetMute(0, None)
            return {"available": True, "result": "Volume unmuted Boss."}
        except Exception as exc:
            return {"available": True, "result": None, "error": str(exc)}

    def set_volume(self, level: float) -> Dict[str, Any]:
        try:
            level = max(0.0, min(1.0, level))
            vol = self._get_volume_interface()
            vol.SetMasterVolumeLevelScalar(level, None)
            label = "Maximum" if level >= 1.0 else ("Minimum" if level <= 0.0 else f"{int(level * 100)}%")
            return {"available": True, "result": f"{label} volume activated Boss."}
        except Exception as exc:
            return {"available": True, "result": None, "error": str(exc)}

    # =========================================================================
    # SYSTEM POWER / SESSION CONTROL
    # =========================================================================

    def shutdown(self, delay_sec: int = 5) -> Dict[str, Any]:
        """
        Execute Windows shutdown command.
        SECURITY: The caller (skills/windows_control.py) has already validated
        the session token before reaching this point.
        """
        os.system(f"shutdown /s /t {delay_sec}")
        return {"available": True, "result": "Shutting down computer Boss."}

    def restart(self, delay_sec: int = 5) -> Dict[str, Any]:
        os.system(f"shutdown /r /t {delay_sec}")
        return {"available": True, "result": "Restarting computer Boss."}

    def sleep(self) -> Dict[str, Any]:
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
        return {"available": True, "result": "Going to sleep mode Boss."}

    def lock(self) -> Dict[str, Any]:
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return {"available": True, "result": "Locking computer Boss."}

    def sign_out(self) -> Dict[str, Any]:
        os.system("shutdown /l")
        return {"available": True, "result": "Signing out Boss."}

    def open_settings(self) -> Dict[str, Any]:
        os.system("start ms-settings:")
        return {"available": True, "result": "Opening Windows Settings."}

    # =========================================================================
    # SHELL / TERMINAL
    # =========================================================================

    def get_terminal_command(self) -> List[str]:
        """Return the Windows PowerShell command list."""
        powershell = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
        )
        if os.path.exists(powershell):
            return [powershell]
        cmd = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32", "cmd.exe"
        )
        return [cmd]
