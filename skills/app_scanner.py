"""
ULTRON V3
Smart Application Scanner
"""

import os
import json


APP_DATABASE = "data/apps.json"


SEARCH_LOCATIONS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Users\AZEEZ\AppData\Local"
]


def load_apps():

    if os.path.exists(APP_DATABASE):

        with open(APP_DATABASE, "r") as file:
            return json.load(file)

    return {}



def scan_apps():

    apps = {}


    for location in SEARCH_LOCATIONS:

        if not os.path.exists(location):
            continue


        for root, dirs, files in os.walk(location):

            for file in files:

                if file.lower().endswith(".exe"):

                    name = file[:-4].lower()

                    path = os.path.join(root, file)

                    apps[name] = path


    return apps



def update_apps():

    old_apps = load_apps()

    new_apps = scan_apps()


    added = []


    for name, path in new_apps.items():

        if name not in old_apps:

            added.append(name)


    with open(APP_DATABASE, "w") as file:

        json.dump(new_apps, file, indent=4)


    return added