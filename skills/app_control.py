"""
ULTRON V3
Application Control Skill
"""

import os
import json
import psutil
import pygetwindow as gw


APP_DATABASE = "data/apps.json"


COMMON_APPS = {

    "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",

    "code": r"D:\AZEEZ\Microsoft VS Code\Code.exe",

    "cmd": r"C:\Windows\System32\cmd.exe"

}


def load_apps():

    with open(APP_DATABASE, "r") as file:
        return json.load(file)


def find_app(app_name):

    app_name = app_name.lower().strip()

    # Common apps
    if app_name in COMMON_APPS:
        return COMMON_APPS[app_name]

    apps = load_apps()

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

        except:
            pass

    return False


def focus_app(app_name):

    app_name = app_name.lower()

    try:

        windows = gw.getAllWindows()

        for window in windows:

            if window.title and app_name in window.title.lower():

                if window.isMinimized:
                    window.restore()

                window.activate()

                return True

    except:
        pass

    return False


def open_app(app_name):

    path = find_app(app_name)

    if not path:
        return f"I don't know how to open {app_name}"

    if is_running(app_name):

        focus_app(app_name)

        return f"{app_name} is already open. Bringing it to front"

    if os.path.exists(path):

        os.startfile(path)

        return f"Opening {app_name}"

    return f"{app_name} path not found"


def close_app(app_name):

    app_name = app_name.lower().strip()

    path = find_app(app_name)

    if path:
        process_name = os.path.basename(path)
    else:
        process_name = app_name

        if not process_name.endswith(".exe"):
            process_name += ".exe"

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