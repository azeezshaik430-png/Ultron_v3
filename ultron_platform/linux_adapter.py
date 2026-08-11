"""
ULTRON V3 - Linux Platform Adapter
Implements the PlatformAdapter interface using native Linux mechanisms.

Supported:
    - Application launching via xdg-open / direct subprocess
    - File manager via xdg-open
    - Volume control via amixer (ALSA) or pactl (PulseAudio/PipeWire)
    - Shutdown/restart/sleep via systemctl or legacy shutdown/pm-suspend
    - Lock via loginctl / xdg-screensaver / gnome-screensaver-command
    - Sign-out via loginctl
    - Settings via xdg-open / gnome-control-center / kde-system-settings
    - App search via PATH, /usr/bin, /usr/local/bin, ~/.local/bin

Honest unavailability:
    Features with no universal Linux equivalent return
    {"available": False, "reason": "..."} and never fake success.

Security:
    - All subprocess calls use fixed argument lists (never shell string execution)
    - No automatic sudo execution
    - All privileged operations (shutdown, restart) go through systemctl
      which requires the user session to have appropriate polkit permissions
"""

import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from ultron_platform.interface import CapabilityStatus, PlatformAdapter, PlatformCapabilityError


def _which(cmd: str) -> Optional[str]:
    """Return full path of cmd if found in PATH, else None."""
    return shutil.which(cmd)


def _run_silent(args: List[str]) -> bool:
    """
    Run a subprocess command silently.
    Returns True if exit code == 0, False otherwise.
    Never raises.
    """
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


class LinuxAdapter(PlatformAdapter):
    """
    Linux platform adapter.

    Audio backend is auto-detected at first use:
        - pactl  (PulseAudio / PipeWire)
        - amixer (ALSA)
        - None   → volume operations return available=False

    Window management is best-effort (requires an X11/Wayland environment).
    """

    def __init__(self) -> None:
        self._audio_backend: Optional[str] = None  # lazy detect
        self._capabilities = {
            "open_application": CapabilityStatus.SUPPORTED,
            "open_path": CapabilityStatus.SUPPORTED,
            "focus_window": CapabilityStatus.SUPPORTED if _which("wmctrl") else CapabilityStatus.NOT_AVAILABLE,
            "volume_control": CapabilityStatus.SUPPORTED if (_which("pactl") or _which("amixer") or _which("wpctl")) else CapabilityStatus.NOT_AVAILABLE,
            "system_power": CapabilityStatus.SUPPORTED if _which("systemctl") else CapabilityStatus.NOT_AVAILABLE,
            "brightness_control": CapabilityStatus.SUPPORTED if (_which("brightnessctl") or _which("xrandr")) else CapabilityStatus.NOT_AVAILABLE,
            "wifi_status": CapabilityStatus.SUPPORTED if (_which("nmcli") or _which("iwconfig")) else CapabilityStatus.NOT_AVAILABLE,
            "bluetooth_status": CapabilityStatus.SUPPORTED if _which("bluetoothctl") else CapabilityStatus.NOT_AVAILABLE,
            "clipboard": CapabilityStatus.SUPPORTED if (_which("xclip") or _which("wl-clipboard")) else CapabilityStatus.NOT_AVAILABLE,
            "notifications": CapabilityStatus.SUPPORTED if _which("notify-send") else CapabilityStatus.NOT_AVAILABLE,
            "take_screenshot": CapabilityStatus.SUPPORTED if (_which("scrot") or _which("gnome-screenshot")) else CapabilityStatus.NOT_AVAILABLE,
            "mouse_click": CapabilityStatus.SUPPORTED if _which("xdotool") else CapabilityStatus.NOT_AVAILABLE,
            "keyboard_type": CapabilityStatus.SUPPORTED if _which("xdotool") else CapabilityStatus.NOT_AVAILABLE,
            "process_management": CapabilityStatus.SUPPORTED,
        }

    @property
    def platform_name(self) -> str:
        return "Linux"

    def get_capabilities(self) -> Dict[str, CapabilityStatus]:
        return self._capabilities.copy()

    def get_capability_status(self, capability: str) -> CapabilityStatus:
        return self._capabilities.get(capability, CapabilityStatus.UNSUPPORTED)

    # =========================================================================
    # APPLICATION LAUNCHING
    # =========================================================================

    def open_application(self, path: str) -> Dict[str, Any]:
        """Launch an application by absolute path."""
        if not os.path.exists(path):
            return {"available": True, "result": None, "error": f"Path not found: {path}"}
        try:
            subprocess.Popen([path], close_fds=True)
            name = os.path.basename(path)
            return {"available": True, "result": f"Opening {name}"}
        except Exception as exc:
            return {"available": True, "result": None, "error": str(exc)}

    def get_executable_extension(self) -> str:
        return ""  # Linux executables have no mandatory extension

    def get_app_search_locations(self) -> List[str]:
        """
        Return standard Linux application binary directories.
        """
        candidates = [
            "/usr/bin",
            "/usr/local/bin",
            "/usr/share/applications",
            os.path.expanduser("~/.local/bin"),
            os.path.expanduser("~/.local/share/applications"),
            "/opt",
        ]
        return [p for p in candidates if os.path.isdir(p)]

    def get_user_appdata_path(self) -> str:
        """
        Return the XDG_DATA_HOME directory, defaulting to ~/.local/share.
        """
        xdg = os.environ.get("XDG_DATA_HOME", "")
        if xdg and os.path.isdir(xdg):
            return xdg
        path = os.path.join(os.path.expanduser("~"), ".local", "share")
        os.makedirs(path, exist_ok=True)
        return path

    # =========================================================================
    # WINDOW MANAGEMENT
    # =========================================================================

    def focus_window(self, app_name: str) -> Dict[str, Any]:
        """
        Attempt to focus a window by name using wmctrl (if available).
        wmctrl is a common X11 utility; not available in all environments.
        """
        wmctrl = _which("wmctrl")
        if not wmctrl:
            return {
                "available": False,
                "reason": "wmctrl not found. Install wmctrl for window management on Linux.",
            }
        try:
            result = subprocess.run(
                [wmctrl, "-a", app_name],
                capture_output=True,
                check=False,
            )
            success = result.returncode == 0
            return {"available": True, "result": success}
        except Exception as exc:
            return {"available": True, "result": False, "error": str(exc)}

    # =========================================================================
    # FILE MANAGER / PATH OPENING
    # =========================================================================

    def open_path(self, path: str) -> Dict[str, Any]:
        """
        Open a path using xdg-open (works for files, directories, and URLs).
        Falls back to nautilus/dolphin/thunar for directory browsing if available.
        """
        xdg_open = _which("xdg-open")
        if xdg_open:
            try:
                subprocess.Popen([xdg_open, path], close_fds=True)
                return {"available": True, "result": f"Opening {path}"}
            except Exception as exc:
                return {"available": True, "result": None, "error": str(exc)}

        # Fallback: try common file managers directly
        for fm in ["nautilus", "dolphin", "thunar", "pcmanfm", "nemo"]:
            fm_path = _which(fm)
            if fm_path and os.path.isdir(path):
                try:
                    subprocess.Popen([fm_path, path], close_fds=True)
                    return {"available": True, "result": f"Opening {path}"}
                except Exception:
                    continue

        return {
            "available": False,
            "reason": "xdg-open not found and no known file manager is available.",
        }

    def get_search_locations(self) -> List[str]:
        """
        Return common Linux user directories to search for files.
        """
        locations = [
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~"),
        ]
        return [loc for loc in locations if os.path.exists(loc)]

    def get_common_dirs(self) -> Dict[str, Optional[str]]:
        """Return common Linux user directories."""
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

    def _detect_audio_backend(self) -> Optional[str]:
        """Auto-detect available audio control backend."""
        if self._audio_backend is not None:
            return self._audio_backend
        if _which("pactl"):
            self._audio_backend = "pactl"
        elif _which("amixer"):
            self._audio_backend = "amixer"
        else:
            self._audio_backend = "none"
        return self._audio_backend

    def _pactl_volume_up(self, step_pct: int) -> bool:
        return _run_silent(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"+{step_pct}%"])

    def _pactl_volume_down(self, step_pct: int) -> bool:
        return _run_silent(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"-{step_pct}%"])

    def _pactl_mute(self, mute: bool) -> bool:
        return _run_silent(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if mute else "0"])

    def _pactl_set_volume(self, level_pct: int) -> bool:
        return _run_silent(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level_pct}%"])

    def _amixer_volume_up(self, step_pct: int) -> bool:
        return _run_silent(["amixer", "-q", "sset", "Master", f"{step_pct}%+"])

    def _amixer_volume_down(self, step_pct: int) -> bool:
        return _run_silent(["amixer", "-q", "sset", "Master", f"{step_pct}%-"])

    def _amixer_mute(self, mute: bool) -> bool:
        state = "mute" if mute else "unmute"
        return _run_silent(["amixer", "-q", "sset", "Master", state])

    def _amixer_set_volume(self, level_pct: int) -> bool:
        return _run_silent(["amixer", "-q", "sset", "Master", f"{level_pct}%"])

    def volume_up(self, step: float = 0.1) -> Dict[str, Any]:
        backend = self._detect_audio_backend()
        step_pct = int(step * 100)
        if backend == "pactl":
            ok = self._pactl_volume_up(step_pct)
        elif backend == "amixer":
            ok = self._amixer_volume_up(step_pct)
        else:
            return {"available": False, "reason": "No audio control utility found (pactl or amixer required)."}
        return {"available": True, "result": "Volume increased Boss." if ok else None,
                "error": None if ok else "Audio command failed."}

    def volume_down(self, step: float = 0.1) -> Dict[str, Any]:
        backend = self._detect_audio_backend()
        step_pct = int(step * 100)
        if backend == "pactl":
            ok = self._pactl_volume_down(step_pct)
        elif backend == "amixer":
            ok = self._amixer_volume_down(step_pct)
        else:
            return {"available": False, "reason": "No audio control utility found."}
        return {"available": True, "result": "Volume decreased Boss." if ok else None,
                "error": None if ok else "Audio command failed."}

    def mute(self) -> Dict[str, Any]:
        backend = self._detect_audio_backend()
        if backend == "pactl":
            ok = self._pactl_mute(True)
        elif backend == "amixer":
            ok = self._amixer_mute(True)
        else:
            return {"available": False, "reason": "No audio control utility found."}
        return {"available": True, "result": "Volume muted Boss." if ok else None,
                "error": None if ok else "Audio command failed."}

    def unmute(self) -> Dict[str, Any]:
        backend = self._detect_audio_backend()
        if backend == "pactl":
            ok = self._pactl_mute(False)
        elif backend == "amixer":
            ok = self._amixer_mute(False)
        else:
            return {"available": False, "reason": "No audio control utility found."}
        return {"available": True, "result": "Volume unmuted Boss." if ok else None,
                "error": None if ok else "Audio command failed."}

    def set_volume(self, level: float) -> Dict[str, Any]:
        backend = self._detect_audio_backend()
        level = max(0.0, min(1.0, level))
        level_pct = int(level * 100)
        if backend == "pactl":
            ok = self._pactl_set_volume(level_pct)
        elif backend == "amixer":
            ok = self._amixer_set_volume(level_pct)
        else:
            return {"available": False, "reason": "No audio control utility found."}
        label = "Maximum" if level >= 1.0 else ("Minimum" if level <= 0.0 else f"{level_pct}%")
        return {"available": True, "result": f"{label} volume activated Boss." if ok else None,
                "error": None if ok else "Audio command failed."}

    # =========================================================================
    # SYSTEM POWER / SESSION CONTROL
    # =========================================================================

    def shutdown(self, delay_sec: int = 5) -> Dict[str, Any]:
        """
        Initiate Linux shutdown via systemctl.
        Uses a delay expressed in minutes for systemctl compatibility (minimum: now).
        SECURITY: Token validation must be performed by the caller before this is invoked.
        """
        systemctl = _which("systemctl")
        if systemctl:
            # systemctl poweroff does not support per-second delay; schedule immediately
            ok = _run_silent([systemctl, "poweroff"])
            if ok:
                return {"available": True, "result": "Shutting down computer Boss."}

        # Fallback: traditional shutdown command (requires sudo or polkit)
        shutdown_cmd = _which("shutdown")
        if shutdown_cmd:
            ok = _run_silent([shutdown_cmd, "-h", "+0"])
            if ok:
                return {"available": True, "result": "Shutting down computer Boss."}

        return {
            "available": False,
            "reason": "shutdown/systemctl not found or insufficient permissions.",
        }

    def restart(self, delay_sec: int = 5) -> Dict[str, Any]:
        systemctl = _which("systemctl")
        if systemctl:
            ok = _run_silent([systemctl, "reboot"])
            if ok:
                return {"available": True, "result": "Restarting computer Boss."}

        shutdown_cmd = _which("shutdown")
        if shutdown_cmd:
            ok = _run_silent([shutdown_cmd, "-r", "+0"])
            if ok:
                return {"available": True, "result": "Restarting computer Boss."}

        return {
            "available": False,
            "reason": "systemctl/shutdown not found or insufficient permissions.",
        }

    def sleep(self) -> Dict[str, Any]:
        systemctl = _which("systemctl")
        if systemctl:
            ok = _run_silent([systemctl, "suspend"])
            if ok:
                return {"available": True, "result": "Going to sleep mode Boss."}

        pm_suspend = _which("pm-suspend")
        if pm_suspend:
            ok = _run_silent([pm_suspend])
            if ok:
                return {"available": True, "result": "Going to sleep mode Boss."}

        return {
            "available": False,
            "reason": "systemctl suspend / pm-suspend not available.",
        }

    def lock(self) -> Dict[str, Any]:
        """
        Lock the session using the best available mechanism.
        Tries: loginctl, gnome-screensaver-command, xdg-screensaver, xscreensaver-command.
        """
        for cmd, args in [
            ("loginctl", ["loginctl", "lock-session"]),
            ("gnome-screensaver-command", ["gnome-screensaver-command", "--lock"]),
            ("xdg-screensaver", ["xdg-screensaver", "lock"]),
            ("xscreensaver-command", ["xscreensaver-command", "-lock"]),
        ]:
            if _which(cmd):
                ok = _run_silent(args)
                if ok:
                    return {"available": True, "result": "Locking computer Boss."}

        return {
            "available": False,
            "reason": "No session lock utility found (loginctl, gnome-screensaver-command, xdg-screensaver).",
        }

    def sign_out(self) -> Dict[str, Any]:
        """
        Log out of the current session.
        Tries: loginctl, gnome-session-quit, kde-session-quit.
        """
        loginctl = _which("loginctl")
        if loginctl:
            ok = _run_silent([loginctl, "terminate-session", "self"])
            if ok:
                return {"available": True, "result": "Signing out Boss."}

        for cmd, args in [
            ("gnome-session-quit", ["gnome-session-quit", "--logout", "--no-prompt"]),
            ("qdbus", ["qdbus", "org.kde.ksmserver", "/KSMServer", "logout", "0", "0", "0"]),
        ]:
            if _which(cmd):
                ok = _run_silent(args)
                if ok:
                    return {"available": True, "result": "Signing out Boss."}

        return {
            "available": False,
            "reason": "No sign-out utility found (loginctl, gnome-session-quit).",
        }

    def open_settings(self) -> Dict[str, Any]:
        """Open the OS settings panel using best available method."""
        for cmd in ["gnome-control-center", "systemsettings5", "kde-system-settings", "xfce4-settings-manager"]:
            path = _which(cmd)
            if path:
                try:
                    subprocess.Popen([path], close_fds=True)
                    return {"available": True, "result": f"Opening system settings ({cmd})."}
                except Exception:
                    continue

        # Fallback via xdg-open
        xdg = _which("xdg-open")
        if xdg:
            try:
                subprocess.Popen([xdg, "settings://"], close_fds=True)
                return {"available": True, "result": "Opening system settings."}
            except Exception:
                pass

        return {
            "available": False,
            "reason": "No system settings utility found.",
        }

    # =========================================================================
    # SHELL / TERMINAL
    # =========================================================================

    def get_terminal_command(self) -> List[str]:
        """Return the best available terminal emulator command."""
        for term in ["gnome-terminal", "konsole", "xfce4-terminal", "xterm", "bash"]:
            path = _which(term)
            if path:
                return [path]
        return ["sh"]

    # =========================================================================
    # EXTENDED HARDWARE & OS CONTROLS
    # =========================================================================

    def set_brightness(self, level: float) -> Dict[str, Any]:
        val = max(0, min(100, int(level * 100)))
        if _which("brightnessctl"):
            try:
                subprocess.run(["brightnessctl", "set", f"{val}%"], check=True)
                return {"available": True, "result": f"Brightness set to {val}%.", "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "brightnessctl is not installed on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def get_brightness(self) -> Dict[str, Any]:
        if _which("brightnessctl"):
            try:
                res = subprocess.run(["brightnessctl", "info"], capture_output=True, text=True, check=True)
                return {"available": True, "result": res.stdout, "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "brightnessctl is not installed on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def get_wifi_status(self) -> Dict[str, Any]:
        if _which("nmcli"):
            try:
                res = subprocess.run(["nmcli", "radio", "wifi"], capture_output=True, text=True, check=True)
                return {"available": True, "result": res.stdout.strip(), "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "nmcli is not installed on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def get_bluetooth_status(self) -> Dict[str, Any]:
        if _which("bluetoothctl"):
            try:
                res = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True, check=True)
                return {"available": True, "result": res.stdout, "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "bluetoothctl is not installed on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def get_clipboard(self) -> Dict[str, Any]:
        if _which("xclip"):
            try:
                res = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, check=True)
                return {"available": True, "result": res.stdout, "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        elif _which("wl-paste"):
            try:
                res = subprocess.run(["wl-paste"], capture_output=True, text=True, check=True)
                return {"available": True, "result": res.stdout, "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "Neither xclip nor wl-clipboard found on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def set_clipboard(self, text: str) -> Dict[str, Any]:
        if _which("xclip"):
            try:
                p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True)
                p.communicate(input=text)
                return {"available": True, "result": "Copied to clipboard.", "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "xclip utility not installed on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def send_notification(self, title: str, message: str) -> Dict[str, Any]:
        if _which("notify-send"):
            try:
                subprocess.run(["notify-send", title, message], check=True)
                return {"available": True, "result": "Notification sent.", "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "notify-send is not installed on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def take_screenshot(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        out = output_path or "/tmp/ultron_screenshot.png"
        if _which("scrot"):
            try:
                subprocess.run(["scrot", out], check=True)
                return {"available": True, "result": f"Screenshot saved to {out}.", "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        elif _which("gnome-screenshot"):
            try:
                subprocess.run(["gnome-screenshot", "-f", out], check=True)
                return {"available": True, "result": f"Screenshot saved to {out}.", "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "Neither scrot nor gnome-screenshot found on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def mouse_click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        if _which("xdotool"):
            try:
                btn_num = "1" if button == "left" else "3"
                subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", btn_num], check=True)
                return {"available": True, "result": f"Mouse clicked at ({x}, {y}).", "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "xdotool is not installed on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}

    def keyboard_type(self, text: str) -> Dict[str, Any]:
        if _which("xdotool"):
            try:
                subprocess.run(["xdotool", "type", text], check=True)
                return {"available": True, "result": f"Typed '{text}'.", "status": CapabilityStatus.SUPPORTED}
            except Exception as e:
                return {"available": False, "reason": str(e), "status": CapabilityStatus.NOT_AVAILABLE}
        return {"available": False, "reason": "xdotool is not installed on this Linux environment.", "status": CapabilityStatus.NOT_AVAILABLE}
