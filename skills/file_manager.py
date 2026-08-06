"""
ULTRON V3
File Manager
"""

import os
import subprocess


def open_downloads():

    path = os.path.join(
        os.path.expanduser("~"),
        "Downloads"
    )

    subprocess.Popen(["explorer", path])

    return "Opening Downloads."


def open_desktop():

    path = os.path.join(
        os.path.expanduser("~"),
        "Desktop"
    )

    subprocess.Popen(["explorer", path])

    return "Opening Desktop."


def open_documents():

    path = os.path.join(
        os.path.expanduser("~"),
        "Documents"
    )

    subprocess.Popen(["explorer", path])

    return "Opening Documents."


def open_d_drive():

    subprocess.Popen(["explorer", "D:\\"])

    return "Opening D drive."


def open_c_drive():

    subprocess.Popen(["explorer", "C:\\"])

    return "Opening C drive."