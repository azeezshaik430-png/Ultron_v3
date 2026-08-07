"""
ULTRON V3
Smart Application Scanner
"""

import os
import json
from core.config import config
from core.logger import logger


APP_DATABASE = config.get_data_path("apps.json")

SEARCH_LOCATIONS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Users\AZEEZ\AppData\Local",
]


def load_apps():
    if os.path.exists(APP_DATABASE):
        try:
            with open(APP_DATABASE, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as e:
            logger.error(f"Error loading apps database: {e}")
    return {}


def save_apps(apps):
    """Save apps dictionary to apps.json."""
    os.makedirs(os.path.dirname(APP_DATABASE), exist_ok=True)
    with open(APP_DATABASE, "w", encoding="utf-8") as file:
        json.dump(apps, file, indent=4)
    logger.info(f"Saved {len(apps)} apps to database.")


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

    save_apps(new_apps)
    return added