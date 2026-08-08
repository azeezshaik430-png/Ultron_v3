"""
ULTRON V3
Application Control Skill

Cross-platform: delegates OS-specific operations to the platform adapter.
"""

import os
import json
import psutil
import ultron_platform


APP_DATABASE = "data/apps.json"


def _adapter():
    """Return the current platform adapter via module reference (supports test patching)."""
    return ultron_platform.get_platform_adapter()


def load_apps():
    with open(APP_DATABASE, "r") as file:
        return json.load(file)


def find_app(app_name):
    app_name = app_name.lower().strip()

    # Check common terminal launchers via platform adapter
    adapter = _adapter()
    if app_name in ["terminal", "shell", "console"]:
        terminal_cmd = adapter.get_terminal_command()
        if terminal_cmd:
            return terminal_cmd[0]

    apps = {}
    try:
        apps = load_apps()
    except Exception:
        pass

    # Exact match
    if app_name in apps:
        return apps[app_name]

    # Partial match
    for name, path in apps.items():
        if app_name in name.lower():
            return path

    return None


def is_running(app_name):
    app_name = app_name.lower()

    for process in psutil.process_iter(["name"]):
        try:
            process_name = process.info["name"]
            if process_name and app_name in process_name.lower():
                return True
        except Exception:
            pass

    return False


def focus_app(app_name):
    """Focus an application window using the platform adapter."""
    result = _adapter().focus_window(app_name)
    if not result.get("available", False):
        return False
    return result.get("result", False)


def open_app(app_name):
    path = find_app(app_name)

    if not path:
        return f"I don't know how to open {app_name}"

    if is_running(app_name):
        focus_app(app_name)
        return f"{app_name} is already open. Bringing it to front"

    if os.path.exists(path):
        result = _adapter().open_application(path)
        if result.get("result"):
            return f"Opening {app_name}"
        error = result.get("error", "")
        return f"{app_name} could not be opened: {error}" if error else f"{app_name} path not found"

    return f"{app_name} path not found"


def close_app(app_name):
    app_name = app_name.lower().strip()

    path = find_app(app_name)

    if path:
        process_name = os.path.basename(path)
    else:
        process_name = app_name
        # On Windows, add .exe if not present; on other platforms leave as-is
        ext = _adapter().get_executable_extension()
        if ext and not process_name.endswith(ext):
            process_name += ext

    closed = False

    for process in psutil.process_iter(["pid", "name"]):
        try:
            if (
                process.info["name"]
                and process.info["name"].lower() == process_name.lower()
            ):
                process.terminate()
                process.wait(timeout=3)
                closed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass

    if closed:
        return f"Closing {app_name}"

    return f"{app_name} is not running"