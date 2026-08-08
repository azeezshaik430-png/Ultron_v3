"""
ULTRON V3
Dynamic File Search

Cross-platform: uses platform adapter for opening found items and for
determining platform-appropriate search locations.
"""

import os
import ultron_platform


def _adapter():
    return ultron_platform.get_platform_adapter()


def search_item(name):
    name = name.lower()

    search_locations = _adapter().get_search_locations()

    for location in search_locations:
        for root, dirs, files in os.walk(location):
            # folders
            for folder in dirs:
                if name in folder.lower():
                    path = os.path.join(root, folder)
                    result = _adapter().open_path(path)
                    if result.get("available"):
                        return f"Opening {folder}"
                    reason = result.get("reason", "")
                    return f"Found {folder} but cannot open it: {reason}"

            # files
            for file in files:
                if name in file.lower():
                    path = os.path.join(root, file)
                    result = _adapter().open_path(path)
                    if result.get("available"):
                        return f"Opening {file}"
                    reason = result.get("reason", "")
                    return f"Found {file} but cannot open it: {reason}"

    return "I couldn't find that file or folder."