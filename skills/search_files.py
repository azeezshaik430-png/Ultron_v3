"""
ULTRON V3
Dynamic File Search
"""

import os
import subprocess

SEARCH_LOCATIONS = [

    os.path.expanduser("~/Desktop"),

    os.path.expanduser("~/Documents"),

    os.path.expanduser("~/Downloads"),

    "D:\\",

    "C:\\"

]


def search_item(name):

    name = name.lower()

    for location in SEARCH_LOCATIONS:

        for root, dirs, files in os.walk(location):

            # folders

            for folder in dirs:

                if name in folder.lower():

                    path = os.path.join(root, folder)

                    subprocess.Popen(["explorer", path])

                    return f"Opening {folder}"

            # files

            for file in files:

                if name in file.lower():

                    path = os.path.join(root, file)

                    os.startfile(path)

                    return f"Opening {file}"

    return "I couldn't find that file or folder."