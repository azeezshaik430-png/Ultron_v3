"""
ULTRON V3
Smart Application Scanner

Cross-platform: uses platform adapter for OS-specific search locations and
executable extension. The scanning logic itself is platform-neutral.
"""

import os
import json
import ultron_platform
from core.config import config
from core.logger import logger


APP_DATABASE = config.get_data_path("apps.json")


def _adapter():
    return ultron_platform.get_platform_adapter()


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
    """
    Scan platform-appropriate directories for installed applications.
    Uses the platform adapter to determine search locations and executable
    extension rather than hardcoding Windows-specific paths.
    """
    adapter = _adapter()
    search_locations = adapter.get_app_search_locations()
    ext = adapter.get_executable_extension()

    apps = {}
    for location in search_locations:
        if not os.path.exists(location):
            continue
        for root, dirs, files in os.walk(location):
            for file in files:
                file_lower = file.lower()
                if ext:
                    if file_lower.endswith(ext):
                        name = file[: -len(ext)].lower()
                        path = os.path.join(root, file)
                        apps[name] = path
                else:
                    if "." not in file or file_lower.endswith((".sh", ".bin", ".run")):
                        full_path = os.path.join(root, file)
                        if os.access(full_path, os.X_OK):
                            name = file.lower()
                            apps[name] = full_path
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