"""
ULTRON V3
Application Control Skill
"""

import os


# Common app locations

APPS = {

    "brave": r"C:\Users\AZEEZ\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe",

    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",

}


def open_app(app_name):

    app_name = app_name.lower()


    if app_name in APPS:

        path = APPS[app_name]

        if os.path.exists(path):

            os.startfile(path)

            return f"Opening {app_name}"

        else:

            return f"{app_name} path not found"


    return f"I don't know how to open {app_name}"