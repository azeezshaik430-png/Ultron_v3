"""
ULTRON V3 - System Control Agent
Phase 2B.2 System Control Agent.
Integrates existing skills: app_control, app_scanner, file_manager, search_files, system_control, volume_control, windows_control.
"""

import os
from typing import Dict, Any, Optional, List
from agents.base_ultron_agent import BaseUltronAgent

import skills.app_control as app_control
import skills.app_scanner as app_scanner
import skills.file_manager as file_manager
import skills.search_files as search_files
import skills.system_control as system_control
import skills.volume_control as volume_control
import skills.windows_control as windows_control


class SystemAgent(BaseUltronAgent):
    """
    System Control Domain Agent.
    
    Purpose:
    - Provides safe execution of application control, system status monitoring,
      file search & explorer opening, Windows session control, and audio volume control.
      
    Security Guardrails:
    - Requires explicit confirmation or token for destructive operations (shutdown, restart, delete, force kill).
    - Prevents arbitrary/unrestricted shell execution.
    """

    def __init__(
        self,
        agent_id: str = "system_agent",
        name: str = "System Control Agent",
        description: str = "Manages OS control, application discovery, file navigation, volume control, and system status.",
        bus: Optional[Any] = None,
        version: str = "1.0.0",
    ) -> None:
        capabilities = [
            "application_control",
            "system_info",
            "file_operations",
            "windows_control",
            "volume_control",
            "app_discovery",
            "system_status",
        ]
        supported_skills = [
            "app_control",
            "app_scanner",
            "file_manager",
            "search_files",
            "system_control",
            "volume_control",
            "windows_control",
        ]
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=capabilities,
            supported_skills=supported_skills,
            bus=bus,
            version=version,
        )

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        """
        Execute system domain payload.
        Payload structure:
        {
            "action": str,           # e.g., "open_app", "get_battery", "volume_up", etc.
            "app_name": str,         # for app control
            "query": str,            # for file search
            "confirmed": bool,       # for destructive actions
            "force": bool,           # for process terminate
            "token": str,            # session validation token
            ...
        }
        """
        if not isinstance(payload, dict):
            task_str = str(payload)
            return self._handle_raw_string_task(task_str)

        action = payload.get("action", "").lower().strip()
        if not action:
            cmd = payload.get("task") or payload.get("command") or ""
            if cmd:
                return self._handle_raw_string_task(str(cmd))
            raise ValueError("Payload missing required 'action' or 'task' field.")

        # --- APPLICATION CONTROL & DISCOVERY ---
        if action in ["open_app", "open"]:
            app_name = payload.get("app_name") or payload.get("target") or payload.get("app")
            if not app_name:
                raise ValueError("open_app requires 'app_name' parameter.")
            return app_control.open_app(app_name)

        elif action in ["close_app", "close", "terminate_app"]:
            app_name = payload.get("app_name") or payload.get("target") or payload.get("app")
            if not app_name:
                raise ValueError("close_app requires 'app_name' parameter.")
            if payload.get("force") and not payload.get("confirmed", False):
                return "Security block: Forced termination of process requires explicit user confirmation."
            return app_control.close_app(app_name)

        elif action in ["focus_app", "focus"]:
            app_name = payload.get("app_name") or payload.get("target")
            if not app_name:
                raise ValueError("focus_app requires 'app_name' parameter.")
            return app_control.focus_app(app_name)

        elif action in ["is_running", "check_running"]:
            app_name = payload.get("app_name") or payload.get("target")
            if not app_name:
                raise ValueError("is_running requires 'app_name' parameter.")
            return app_control.is_running(app_name)

        elif action in ["scan_apps", "update_apps", "app_discovery"]:
            return app_scanner.update_apps()

        elif action in ["list_apps", "load_apps"]:
            return app_scanner.load_apps()

        # --- SYSTEM INFO & STATUS ---
        elif action in ["get_time", "time"]:
            return system_control.get_time()

        elif action in ["get_date", "date"]:
            return system_control.get_date()

        elif action in ["get_battery", "battery"]:
            return system_control.get_battery()

        elif action in ["system_status", "status", "system_info"]:
            return system_control.system_status()

        # --- FILE OPERATIONS ---
        elif action in ["open_downloads", "downloads"]:
            return file_manager.open_downloads()

        elif action in ["open_desktop", "desktop"]:
            return file_manager.open_desktop()

        elif action in ["open_documents", "documents"]:
            return file_manager.open_documents()

        elif action in ["open_d_drive", "d_drive"]:
            return file_manager.open_d_drive()

        elif action in ["open_c_drive", "c_drive"]:
            return file_manager.open_c_drive()

        elif action in ["search_files", "search_item", "file_search"]:
            query = payload.get("query") or payload.get("name") or payload.get("target")
            if not query:
                raise ValueError("search_files requires 'query' or 'name' parameter.")
            return search_files.search_item(query)

        elif action in ["delete_file", "remove_file"]:
            # DESTRUCTIVE FILE ACTION PROTECTION
            path = payload.get("path") or payload.get("file")
            if not path:
                raise ValueError("delete_file requires 'path' parameter.")
            if not payload.get("confirmed", False):
                return f"Security block: Destructive action delete_file on '{path}' requires explicit user confirmation (confirmed: True)."
            if os.path.exists(path):
                os.remove(path)
                return f"Successfully deleted file '{path}'."
            return f"File '{path}' not found."

        # --- VOLUME CONTROL ---
        elif action in ["volume_up", "raise_volume"]:
            return volume_control.volume_up()

        elif action in ["volume_down", "lower_volume"]:
            return volume_control.volume_down()

        elif action in ["mute"]:
            return volume_control.mute()

        elif action in ["unmute"]:
            return volume_control.unmute()

        elif action in ["max_volume"]:
            return volume_control.max_volume()

        elif action in ["min_volume"]:
            return volume_control.min_volume()

        # --- WINDOWS SESSION CONTROL ---
        elif action in ["lock_pc", "lock"]:
            return windows_control.lock_pc()

        elif action in ["open_settings", "settings"]:
            return windows_control.open_settings()

        elif action in ["sleep_pc", "sleep"]:
            return windows_control.sleep_pc()

        elif action in ["sign_out_pc", "sign_out"]:
            return windows_control.sign_out_pc()

        elif action in ["shutdown_pc", "shutdown"]:
            return windows_control.shutdown_pc()

        elif action in ["restart_pc", "restart"]:
            # DESTRUCTIVE RESTART PROTECTION
            if not payload.get("confirmed", False):
                return "Security block: Restart computer requires explicit user confirmation (confirmed: True)."
            return windows_control.restart_pc()

        else:
            raise ValueError(f"Unknown or unsupported system action: '{action}'")

    def _handle_raw_string_task(self, task_str: str) -> str:
        """Helper to match basic raw string commands for legacy routing."""
        task_lower = task_str.lower().strip()
        if "time" in task_lower:
            return system_control.get_time()
        elif "date" in task_lower:
            return system_control.get_date()
        elif "battery" in task_lower:
            return system_control.get_battery()
        elif "status" in task_lower:
            return system_control.system_status()
        elif "volume up" in task_lower:
            return volume_control.volume_up()
        elif "volume down" in task_lower:
            return volume_control.volume_down()
        elif "mute" in task_lower:
            return volume_control.mute()
        elif "lock" in task_lower:
            return windows_control.lock_pc()
        elif "settings" in task_lower:
            return windows_control.open_settings()
        elif "downloads" in task_lower:
            return file_manager.open_downloads()
        elif "desktop" in task_lower:
            return file_manager.open_desktop()
        elif "documents" in task_lower:
            return file_manager.open_documents()
        elif task_lower.startswith("open "):
            app_name = task_lower[5:].strip()
            return app_control.open_app(app_name)
        elif task_lower.startswith("close "):
            app_name = task_lower[6:].strip()
            return app_control.close_app(app_name)
        else:
            return f"SystemAgent received task: '{task_str}'"
