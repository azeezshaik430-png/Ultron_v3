"""
ULTRON V3 - macOS Platform Adapter
Implementation of PlatformAdapter contract for macOS (Darwin).

This file provides macOS native commands via osascript, open, pmset, pbcopy, screencapture, etc.
On non-macOS development environments (Windows/Linux), static/mock testing validates the contract interface.
"""

import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
from ultron_platform.interface import CapabilityStatus, PlatformAdapter


class MacOSAdapter(PlatformAdapter):
    """
    macOS Platform Adapter implementation.
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
            "bluetooth_status": CapabilityStatus.NOT_AVAILABLE,
            "clipboard": CapabilityStatus.SUPPORTED,
            "notifications": CapabilityStatus.SUPPORTED,
            "take_screenshot": CapabilityStatus.SUPPORTED,
            "mouse_click": CapabilityStatus.REQUIRES_PERMISSION,
            "keyboard_type": CapabilityStatus.REQUIRES_PERMISSION,
            "process_management": CapabilityStatus.SUPPORTED,
        }

    # =========================================================================
    # IDENTITY & CAPABILITIES
    # =========================================================================

    @property
    def platform_name(self) -> str:
        return "macOS"

    def get_capabilities(self) -> Dict[str, CapabilityStatus]:
        return self._capabilities.copy()

    def get_capability_status(self, capability: str) -> CapabilityStatus:
        return self._capabilities.get(capability, CapabilityStatus.UNSUPPORTED)

    # =========================================================================
    # APPLICATION LAUNCHING
    # =========================================================================

    def open_application(self, path: str) -> Dict[str, Any]:
        if not path:
            return {"available": False, "reason": "No path provided.", "status": CapabilityStatus.NOT_AVAILABLE}

        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS open_application cannot execute on non-macOS environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }

        try:
            cmd = ["open", path] if path.endswith(".app") or "/" in path else ["open", "-a", path]
            subprocess.run(cmd, check=True)
            return {"available": True, "result": f"Opening {path} on macOS.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def get_executable_extension(self) -> str:
        return ".app"

    def get_app_search_locations(self) -> List[str]:
        return [
            "/Applications",
            "/System/Applications",
            os.path.expanduser("~/Applications"),
        ]

    def get_user_appdata_path(self) -> str:
        return os.path.expanduser("~/Library/Application Support")

    # =========================================================================
    # WINDOW MANAGEMENT
    # =========================================================================

    def focus_window(self, app_name: str) -> Dict[str, Any]:
        if not app_name:
            return {"available": False, "reason": "No application name provided.", "status": CapabilityStatus.NOT_AVAILABLE}

        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS focus_window requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }

        try:
            script = f'tell application "{app_name}" to activate'
            subprocess.run(["osascript", "-e", script], check=True)
            return {"available": True, "result": True, "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    # =========================================================================
    # FILE MANAGER / PATH OPENING
    # =========================================================================

    def open_path(self, path: str) -> Dict[str, Any]:
        if not path:
            return {"available": False, "reason": "No path provided.", "status": CapabilityStatus.NOT_AVAILABLE}

        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS open_path requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }

        try:
            subprocess.run(["open", path], check=True)
            return {"available": True, "result": f"Opening {path}.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def get_search_locations(self) -> List[str]:
        home = os.path.expanduser("~")
        return [
            os.path.join(home, "Desktop"),
            os.path.join(home, "Documents"),
            os.path.join(home, "Downloads"),
            "/Applications",
            home,
        ]

    def get_common_dirs(self) -> Dict[str, Optional[str]]:
        home = os.path.expanduser("~")
        dirs = {
            "downloads": os.path.join(home, "Downloads"),
            "desktop": os.path.join(home, "Desktop"),
            "documents": os.path.join(home, "Documents"),
            "home": home,
        }
        return {k: v if os.path.exists(v) else None for k, v in dirs.items()}

    # =========================================================================
    # VOLUME / AUDIO CONTROL
    # =========================================================================

    def _run_osascript_volume(self, script: str) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS volume control requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            subprocess.run(["osascript", "-e", script], check=True)
            return {"available": True, "result": "macOS volume adjusted.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def volume_up(self, step: float = 0.1) -> Dict[str, Any]:
        vol_change = int(step * 100)
        return self._run_osascript_volume(f"set volume output volume ((output volume of (get volume settings)) + {vol_change})")

    def volume_down(self, step: float = 0.1) -> Dict[str, Any]:
        vol_change = int(step * 100)
        return self._run_osascript_volume(f"set volume output volume ((output volume of (get volume settings)) - {vol_change})")

    def mute(self) -> Dict[str, Any]:
        return self._run_osascript_volume("set volume output muted true")

    def unmute(self) -> Dict[str, Any]:
        return self._run_osascript_volume("set volume output muted false")

    def set_volume(self, level: float) -> Dict[str, Any]:
        vol_int = max(0, min(100, int(level * 100)))
        return self._run_osascript_volume(f"set volume output volume {vol_int}")

    # =========================================================================
    # SYSTEM POWER / SESSION CONTROL
    # =========================================================================

    def shutdown(self, delay_sec: int = 5) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS shutdown requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            subprocess.run(["osascript", "-e", 'tell app "System Events" to shut down'], check=True)
            return {"available": True, "result": "macOS shutdown initiated.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def restart(self, delay_sec: int = 5) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS restart requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            subprocess.run(["osascript", "-e", 'tell app "System Events" to restart'], check=True)
            return {"available": True, "result": "macOS restart initiated.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def sleep(self) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS sleep requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            subprocess.run(["pmset", "sleepnow"], check=True)
            return {"available": True, "result": "macOS entering sleep mode.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def lock(self) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS lock requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            subprocess.run(["pmset", "displaysleepnow"], check=True)
            return {"available": True, "result": "macOS screen locked.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def sign_out(self) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS log out requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            subprocess.run(["osascript", "-e", 'tell app "System Events" to log out'], check=True)
            return {"available": True, "result": "macOS logging out.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def open_settings(self) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS System Settings requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            subprocess.run(["open", "x-apple.systempreferences:"], check=True)
            return {"available": True, "result": "Opening macOS System Settings.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    # =========================================================================
    # SHELL / TERMINAL
    # =========================================================================

    def get_terminal_command(self) -> List[str]:
        return ["open", "-a", "Terminal"]

    # =========================================================================
    # EXTENDED HARDWARE & OS CONTROLS
    # =========================================================================

    def set_brightness(self, level: float) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS brightness control requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        return {"available": False, "reason": "Brightness control on macOS requires native CoreDisplay API.", "status": CapabilityStatus.NOT_IMPLEMENTED}

    def get_brightness(self) -> Dict[str, Any]:
        return {"available": False, "reason": "Brightness retrieval on macOS requires native CoreDisplay API.", "status": CapabilityStatus.NOT_IMPLEMENTED}

    def get_wifi_status(self) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS Wi-Fi status requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            res = subprocess.run(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                capture_output=True,
                text=True,
            )
            return {"available": True, "result": res.stdout, "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def get_bluetooth_status(self) -> Dict[str, Any]:
        return {"available": False, "reason": "macOS Bluetooth status query not implemented.", "status": CapabilityStatus.NOT_IMPLEMENTED}

    def get_clipboard(self) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS clipboard requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
            return {"available": True, "result": res.stdout, "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def set_clipboard(self, text: str) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS clipboard requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
            return {"available": True, "result": "Copied to clipboard.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def send_notification(self, title: str, message: str) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS notification requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=True)
            return {"available": True, "result": "Notification sent.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def take_screenshot(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS screenshot requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        out = output_path or "/tmp/ultron_screenshot.png"
        try:
            subprocess.run(["screencapture", "-x", out], check=True)
            return {"available": True, "result": f"Screenshot saved to {out}.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}

    def mouse_click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        if shutil.which("cliclick"):
            try:
                subprocess.run(["cliclick", f"c:{x},{y}"], check=True)
                return {"available": True, "result": f"Mouse clicked at ({x}, {y}).", "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "cliclick binary not installed on macOS.", "status": CapabilityStatus.NOT_AVAILABLE}

    def keyboard_type(self, text: str) -> Dict[str, Any]:
        if sys.platform != "darwin":
            return {
                "available": False,
                "reason": "macOS keyboard typing requires darwin runtime environment.",
                "status": CapabilityStatus.NOT_AVAILABLE,
            }
        try:
            script = f'tell application "System Events" to keystroke "{text}"'
            subprocess.run(["osascript", "-e", script], check=True)
            return {"available": True, "result": f"Typed '{text}'.", "status": CapabilityStatus.SUPPORTED}
        except Exception as e:
            return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
