"""
ULTRON V3 - Dynamic Plugin Loader Stub
Scans plugins directory for dynamic extension modules.
"""

import os
import importlib
from typing import Dict, Any
from core.logger import logger
from core.config import config


class PluginLoader:
    """Dynamic Plugin Discovery and Import Loader."""

    def __init__(self) -> None:
        self._plugins: Dict[str, Any] = {}

    def discover_plugins(self) -> None:
        """Scan plugins directory and dynamically import modules."""
        plugin_dir = os.path.join(config.BASE_DIR, "plugins")
        if not os.path.exists(plugin_dir):
            return

        for item in os.listdir(plugin_dir):
            item_path = os.path.join(plugin_dir, item)
            if os.path.isdir(item_path) and not item.startswith("__"):
                try:
                    mod = importlib.import_module(f"plugins.{item}")
                    self._plugins[item] = mod
                    logger.info(f"Loaded plugin module: '{item}'")
                except Exception as e:
                    logger.warning(f"Could not load plugin '{item}': {e}")


# Global Plugin Loader Singleton
plugin_loader = PluginLoader()
