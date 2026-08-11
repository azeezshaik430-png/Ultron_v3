# ULTRON V3 — Platform Support Matrix & Capability Architecture

**Last Updated:** 2026-08-11  
**Architecture:** `PlatformAdapter` Abstract Interface Pattern  
**Development Host:** Windows 11 (x86_64)

---

## 1. Executive Summary

ULTRON V3 adopts a strict platform abstraction layer (`ultron_platform`). All core business logic (Orchestrator, LLM routing, STT/TTS engine, memory system, task engine, security token validation) remains 100% platform-independent. Platform-specific system operations (power management, window control, process manipulation, volume adjustments, hardware queries) are isolated inside concrete platform adapters.

---

## 2. Platform Capability Matrix

| Capability Name | Windows (`WindowsAdapter`) | Linux (`LinuxAdapter`) | macOS (`MacOSAdapter`) | Verification Status on Win Dev Host |
| :--- | :---: | :---: | :---: | :---: |
| **Platform Detection** | `SUPPORTED` | `SUPPORTED` | `SUPPORTED` | **VERIFIED (100%)** |
| **Application Launching** | `SUPPORTED` (`os.startfile`) | `SUPPORTED` (`xdg-open`) | `SUPPORTED` (`open`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **File Manager / Path Open** | `SUPPORTED` (`explorer`) | `SUPPORTED` (`xdg-open`) | `SUPPORTED` (`open`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Window Management** | `SUPPORTED` (`pygetwindow`) | `SUPPORTED` (`wmctrl`) | `SUPPORTED` (`osascript`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Volume Control** | `SUPPORTED` (`pycaw`) | `SUPPORTED` (`pactl`/`amixer`) | `SUPPORTED` (`osascript`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Display Brightness** | `SUPPORTED` (WMI) | `SUPPORTED` (`brightnessctl`) | `NOT_IMPLEMENTED` | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Wi-Fi Interface Status** | `SUPPORTED` (`netsh`) | `SUPPORTED` (`nmcli`) | `SUPPORTED` (`airport`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Bluetooth Device Query** | `SUPPORTED` (PnP) | `SUPPORTED` (`bluetoothctl`) | `NOT_IMPLEMENTED` | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **System Clipboard** | `SUPPORTED` (Win32) | `SUPPORTED` (`xclip`/`wl-paste`) | `SUPPORTED` (`pbcopy`/`pbpaste`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Desktop Notifications** | `SUPPORTED` (WinRT) | `SUPPORTED` (`notify-send`) | `SUPPORTED` (`osascript`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Screen Screenshot** | `SUPPORTED` (Pillow) | `SUPPORTED` (`scrot`) | `SUPPORTED` (`screencapture`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Mouse / Keyboard Control** | `SUPPORTED` (`pyautogui`) | `SUPPORTED` (`xdotool`) | `REQUIRES_PERMISSION` (`cliclick`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **Process Management** | `SUPPORTED` (`psutil`) | `SUPPORTED` (`psutil`) | `SUPPORTED` (`psutil`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |
| **System Power (Shutdown/Restart)**| `SUPPORTED` (`subprocess`) | `SUPPORTED` (`systemctl`) | `SUPPORTED` (`osascript`) | Windows: **VERIFIED** | Linux/macOS: *Static Only* |

---

## 3. Capability Status Enums

Every platform adapter method returns a standardized capability status:

- `SUPPORTED`: Capability is fully implemented and natively supported on the target OS.
- `UNSUPPORTED`: Capability does not exist on the target OS architecture.
- `NOT_AVAILABLE`: Capability utility binary (e.g. `brightnessctl` or `xdotool`) is missing on the environment.
- `REQUIRES_PERMISSION`: Operation requires OS-level Accessibility or Privacy permission (e.g. macOS TCC).
- `NOT_IMPLEMENTED`: Placeholder defined in interface contract for future implementation.

---

## 4. Environment Verification Protocols

1. **Windows Host (Development Environment):**
   - 100% of WindowsAdapter capabilities are runtime verified.
   - Comprehensive unit and integration test suite executed continuously.

2. **Linux Laptop (Target Secondary Environment):**
   - Runtime functionality on Ubuntu/Debian Linux marked **UNVERIFIED** until executed on real Linux hardware.

3. **macOS Host (Target Tertiary Environment):**
   - Runtime functionality on macOS marked **UNVERIFIED** until executed on native Apple hardware.
