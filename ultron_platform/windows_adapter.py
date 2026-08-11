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

from ultron_platform.interface import CapabilityStatus, PlatformAdapter, PlatformCapabilityError


class WindowsAdapter(PlatformAdapter):
    """
    Windows platform adapter.

    Wraps:
        - pycaw  (COM audio endpoint)
        - pygetwindow (window management)
        - os.startfile (file/app launch)
        - Windows shutdown / rundll32 / explorer / powershell
    """

    def __init__(self):
        self._capabilities = {
            "open_application": CapabilityStatus.SUPPORTED,
            "open_path": CapabilityStatus.SUPPORTED,
            "focus_window": CapabilityStatus.SUPPORTED,
            "volume_control": CapabilityStatus.SUPPORTED,
            "system_power": CapabilityStatus.SUPPORTED,
            "brightness_control": CapabilityStatus.SUPPORTED,
            "wifi_status": CapabilityStatus.SUPPORTED,
            "bluetooth_status": CapabilityStatus.SUPPORTED,
            "clipboard": CapabilityStatus.SUPPORTED,
            "notifications": CapabilityStatus.SUPPORTED,
            "take_screenshot": CapabilityStatus.SUPPORTED,
            "mouse_click": CapabilityStatus.SUPPORTED,
            "keyboard_type": CapabilityStatus.SUPPORTED,
            "process_management": CapabilityStatus.SUPPORTED,
        }

    @property
    def platform_name(self) -> str:
        return "Windows"

    def get_capabilities(self) -> Dict[str, CapabilityStatus]:
        return self._capabilities.copy()

    def get_capability_status(self, capability: str) -> CapabilityStatus:
        return self._capabilities.get(capability, CapabilityStatus.UNSUPPORTED)

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
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        return devices.EndpointVolume

    def volume_up(self, step: float = 0.1) -> Dict[str, Any]:
        try:
            vol = self._get_volume_interface()
            current = vol.GetMasterVolumeLevelScalar()
            target = min(current + step, 1.0)
            vol.SetMasterVolumeLevelScalar(target, None)
            new_val = vol.GetMasterVolumeLevelScalar()
            verified = abs(new_val - target) < 0.02 or (target >= 0.98 and new_val >= 0.98)
            pct = int(round(new_val * 100))
            return {
                "available": True,
                "result": f"Volume is now {pct} percent, Boss.",
                "verified": verified,
                "success": True
            }
        except Exception as exc:
            logger.error(f"[WindowsAdapter] volume_up failed: {exc}")
            return {"available": True, "result": None, "error": str(exc), "verified": False, "success": False}

    def volume_down(self, step: float = 0.1) -> Dict[str, Any]:
        try:
            vol = self._get_volume_interface()
            current = vol.GetMasterVolumeLevelScalar()
            target = max(current - step, 0.0)
            vol.SetMasterVolumeLevelScalar(target, None)
            new_val = vol.GetMasterVolumeLevelScalar()
            verified = abs(new_val - target) < 0.02 or (target <= 0.02 and new_val <= 0.02)
            pct = int(round(new_val * 100))
            return {
                "available": True,
                "result": f"Volume is now {pct} percent, Boss.",
                "verified": verified,
                "success": True
            }
        except Exception as exc:
            logger.error(f"[WindowsAdapter] volume_down failed: {exc}")
            return {"available": True, "result": None, "error": str(exc), "verified": False, "success": False}

    def mute(self) -> Dict[str, Any]:
        try:
            vol = self._get_volume_interface()
            vol.SetMute(1, None)
            verified = (vol.GetMute() == 1)
            return {
                "available": True,
                "result": "Volume muted Boss.",
                "verified": verified,
                "success": True
            }
        except Exception as exc:
            logger.error(f"[WindowsAdapter] mute failed: {exc}")
            return {"available": True, "result": None, "error": str(exc), "verified": False, "success": False}

    def unmute(self) -> Dict[str, Any]:
        try:
            vol = self._get_volume_interface()
            vol.SetMute(0, None)
            verified = (vol.GetMute() == 0)
            return {
                "available": True,
                "result": "Volume unmuted Boss.",
                "verified": verified,
                "success": True
            }
        except Exception as exc:
            logger.error(f"[WindowsAdapter] unmute failed: {exc}")
            return {"available": True, "result": None, "error": str(exc), "verified": False, "success": False}

    def set_volume(self, level: float) -> Dict[str, Any]:
        try:
            level = max(0.0, min(1.0, level))
            vol = self._get_volume_interface()
            vol.SetMasterVolumeLevelScalar(level, None)
            new_val = vol.GetMasterVolumeLevelScalar()
            verified = abs(new_val - level) < 0.02
            pct = int(round(new_val * 100))
            label = "Maximum" if pct >= 99 else ("Minimum" if pct <= 1 else f"{pct}%")
            return {
                "available": True,
                "result": f"Volume set to {label} Boss.",
                "verified": verified,
                "success": True
            }
        except Exception as exc:
            logger.error(f"[WindowsAdapter] set_volume failed: {exc}")
            return {"available": True, "result": None, "error": str(exc), "verified": False, "success": False}

    # =========================================================================
    # SYSTEM POWER / SESSION CONTROL
    # =========================================================================

    def shutdown(self, delay_sec: int = 5) -> Dict[str, Any]:
        try:
            import subprocess
            res = subprocess.run(["shutdown", "/s", "/t", str(delay_sec)], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": "Shutting down computer Boss.", "verified": True, "success": True}
            return {"available": True, "result": None, "error": res.stderr.strip(), "verified": False, "success": False}
        except Exception as e:
            return {"available": True, "result": None, "error": str(e), "verified": False, "success": False}

    def restart(self, delay_sec: int = 5) -> Dict[str, Any]:
        try:
            import subprocess
            res = subprocess.run(["shutdown", "/r", "/t", str(delay_sec)], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": "Restarting computer Boss.", "verified": True, "success": True}
            return {"available": True, "result": None, "error": res.stderr.strip(), "verified": False, "success": False}
        except Exception as e:
            return {"available": True, "result": None, "error": str(e), "verified": False, "success": False}

    def sleep(self) -> Dict[str, Any]:
        try:
            import subprocess
            res = subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": "Going to sleep mode Boss.", "verified": True, "success": True}
            return {"available": True, "result": None, "error": res.stderr.strip(), "verified": False, "success": False}
        except Exception as e:
            return {"available": True, "result": None, "error": str(e), "verified": False, "success": False}

    def lock(self) -> Dict[str, Any]:
        try:
            import subprocess
            res = subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": "Locking computer Boss.", "verified": True, "success": True}
            return {"available": True, "result": None, "error": res.stderr.strip(), "verified": False, "success": False}
        except Exception as e:
            return {"available": True, "result": None, "error": str(e), "verified": False, "success": False}

    def sign_out(self) -> Dict[str, Any]:
        try:
            import subprocess
            res = subprocess.run(["shutdown", "/l"], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": "Signing out Boss.", "verified": True, "success": True}
            return {"available": True, "result": None, "error": res.stderr.strip(), "verified": False, "success": False}
        except Exception as e:
            return {"available": True, "result": None, "error": str(e), "verified": False, "success": False}

    def open_settings(self) -> Dict[str, Any]:
        try:
            import subprocess
            subprocess.Popen(["cmd.exe", "/c", "start ms-settings:"], shell=False)
            return {"available": True, "result": "Opening Windows Settings."}
        except Exception as e:
            return {"available": True, "result": None, "error": str(e)}

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

    # =========================================================================
    # EXTENDED HARDWARE & OS CONTROLS
    # =========================================================================

    def set_brightness(self, level: float) -> Dict[str, Any]:
        val = max(0, min(100, int(level * 100)))
        try:
            ps_cmd = f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {val})"
            res = subprocess.run(["powershell", "-Command", ps_cmd], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": f"Brightness set to {val}%.", "status": CapabilityStatus.SUPPORTED}
            return {"available": False, "reason": res.stderr.strip() or "WMI Brightness unsupported on this display.", "status": CapabilityStatus.NOT_AVAILABLE}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def get_brightness(self) -> Dict[str, Any]:
        try:
            ps_cmd = "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness"
            res = subprocess.run(["powershell", "-Command", ps_cmd], shell=False, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip().isdigit():
                val = float(res.stdout.strip()) / 100.0
                return {"available": True, "result": val, "status": CapabilityStatus.SUPPORTED}
            return {"available": False, "reason": "WMI Brightness reading unavailable.", "status": CapabilityStatus.NOT_AVAILABLE}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def get_wifi_status(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["netsh", "wlan", "show", "interfaces"], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": res.stdout, "status": CapabilityStatus.SUPPORTED}
            return {"available": False, "reason": res.stderr.strip(), "status": CapabilityStatus.NOT_AVAILABLE}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def get_bluetooth_status(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["powershell", "-Command", "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName, Status"], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": res.stdout, "status": CapabilityStatus.SUPPORTED}
            return {"available": False, "reason": "Bluetooth PnP query unavailable.", "status": CapabilityStatus.NOT_AVAILABLE}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def get_clipboard(self) -> Dict[str, Any]:
        try:
            res = subprocess.run(["powershell", "-Command", "Get-Clipboard"], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": res.stdout.rstrip("\r\n"), "status": CapabilityStatus.SUPPORTED}
            return {"available": False, "reason": res.stderr.strip(), "status": CapabilityStatus.NOT_AVAILABLE}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def set_clipboard(self, text: str) -> Dict[str, Any]:
        try:
            ps_cmd = f"Set-Clipboard -Value '{text}'"
            res = subprocess.run(["powershell", "-Command", ps_cmd], shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                return {"available": True, "result": "Copied to clipboard.", "status": CapabilityStatus.SUPPORTED}
            return {"available": False, "reason": res.stderr.strip(), "status": CapabilityStatus.NOT_AVAILABLE}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def send_notification(self, title: str, message: str) -> Dict[str, Any]:
        try:
            ps_cmd = f"[reflection.assembly]::loadwithpartialname('System.Windows.Forms'); $n = new-object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; $n.ShowBalloonTip(3000, '{title}', '{message}', [System.Windows.Forms.ToolTipIcon]::Info)"
            subprocess.run(["powershell", "-Command", ps_cmd], shell=False, capture_output=True, text=True)
            return {"available": True, "result": "Notification sent.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def take_screenshot(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        try:
            import pyautogui
            out = output_path or os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "ultron_screenshot.png")
            img = pyautogui.screenshot()
            img.save(out)
            return {"available": True, "result": f"Screenshot saved to {out}.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def mouse_click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        try:
            import pyautogui
            pyautogui.click(x, y, button=button)
            return {"available": True, "result": f"Clicked at ({x}, {y}).", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def keyboard_type(self, text: str) -> Dict[str, Any]:
        try:
            import pyautogui
            pyautogui.typewrite(text)
            return {"available": True, "result": f"Typed '{text}'.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
