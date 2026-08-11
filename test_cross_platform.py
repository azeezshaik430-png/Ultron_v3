"""
ULTRON V3 - Cross-Platform Compatibility Test Suite
Phase: Cross-Platform (post 2B.3)

Tests 20 categories per the cross-platform specification:
    1.  OS detection
    2.  Platform adapter selection
    3.  Path handling
    4.  Configuration paths
    5.  Process abstraction
    6.  Application abstraction
    7.  System information
    8.  Filesystem operations
    9.  Shell abstraction
    10. Permission handling
    11. Unsupported capability handling
    12. Agent initialization
    13. AgentManager integration
    14. MemoryAgent integration
    15. SystemAgent integration
    16. BackgroundTaskAgent integration
    17. PlanningAgent integration
    18. Shutdown / cleanup
    19. Error handling
    20. Security controls

Notes:
    - All tests run on the CURRENT platform (Windows or Linux).
    - Tests that rely on OS-specific behavior are clearly marked.
    - Linux-specific capabilities are tested for correct unavailability
      reporting when running on Windows (and vice versa).
    - No test fabricates results — platform capability flags are used
      to skip tests that cannot run on the current OS.
    - Platform-aware tests use pytest.mark.skipif for honest gating.
"""

import os
import sys
import pytest
import threading
import time
from unittest.mock import patch, MagicMock

# ─────────────────────────────────────────────
# PLATFORM DETECTION HELPERS
# ─────────────────────────────────────────────
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

skip_windows_only = pytest.mark.skipif(
    not IS_WINDOWS, reason="Windows-only capability test"
)
skip_linux_only = pytest.mark.skipif(
    not IS_LINUX, reason="Linux-only capability test"
)


# ─────────────────────────────────────────────
# 1. OS DETECTION
# ─────────────────────────────────────────────

class TestOSDetection:
    def test_platform_module_exists(self):
        """platform module must be importable."""
        import ultron_platform as plt_module
        assert plt_module.is_windows() == IS_WINDOWS
        assert plt_module.is_linux() == IS_LINUX

    def test_platform_name_non_empty(self):
        import ultron_platform as plt_module
        name = plt_module.platform_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_platform_name_consistent_with_sys(self):
        import ultron_platform as plt_module
        name = plt_module.platform_name()
        if IS_WINDOWS:
            assert name == "Windows"
        elif IS_LINUX:
            assert name == "Linux"

    def test_only_one_platform_true(self):
        import ultron_platform as plt_module
        flags = [plt_module.is_windows(), plt_module.is_linux()]
        # At most one should be True
        assert sum(flags) <= 1


# ─────────────────────────────────────────────
# 2. PLATFORM ADAPTER SELECTION
# ─────────────────────────────────────────────

class TestPlatformAdapterSelection:
    def test_get_platform_adapter_returns_object(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        assert adapter is not None

    def test_adapter_is_singleton(self):
        from ultron_platform import get_platform_adapter
        a1 = get_platform_adapter()
        a2 = get_platform_adapter()
        assert a1 is a2

    def test_adapter_has_correct_platform_name(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        if IS_WINDOWS:
            assert adapter.platform_name == "Windows"
        elif IS_LINUX:
            assert adapter.platform_name == "Linux"

    def test_adapter_implements_full_interface(self):
        """Verify the adapter satisfies the PlatformAdapter interface."""
        from ultron_platform.interface import PlatformAdapter
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        assert isinstance(adapter, PlatformAdapter)

    @skip_windows_only
    def test_windows_adapter_type(self):
        from ultron_platform.windows_adapter import WindowsAdapter
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        assert isinstance(adapter, WindowsAdapter)

    @skip_linux_only
    def test_linux_adapter_type(self):
        from ultron_platform.linux_adapter import LinuxAdapter
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        assert isinstance(adapter, LinuxAdapter)


# ─────────────────────────────────────────────
# 3. PATH HANDLING
# ─────────────────────────────────────────────

class TestPathHandling:
    def test_home_directory_exists(self):
        home = os.path.expanduser("~")
        assert os.path.isdir(home)

    def test_adapter_common_dirs_returns_dict(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        dirs = adapter.get_common_dirs()
        assert isinstance(dirs, dict)
        assert "home" in dirs
        assert "downloads" in dirs
        assert "desktop" in dirs
        assert "documents" in dirs

    def test_adapter_common_dirs_home_exists(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        dirs = adapter.get_common_dirs()
        # Home should always be present
        assert dirs.get("home") is not None
        assert os.path.isdir(dirs["home"])

    def test_search_locations_returns_list(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        locs = adapter.get_search_locations()
        assert isinstance(locs, list)
        # All returned paths must exist
        for loc in locs:
            assert os.path.exists(loc), f"Search location does not exist: {loc}"

    def test_user_appdata_path_is_string(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        path = adapter.get_user_appdata_path()
        assert isinstance(path, str)
        assert len(path) > 0

    def test_executable_extension_type(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        ext = adapter.get_executable_extension()
        assert isinstance(ext, str)

    @skip_windows_only
    def test_windows_executable_extension(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        assert adapter.get_executable_extension() == ".exe"

    @skip_linux_only
    def test_linux_executable_extension(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        assert adapter.get_executable_extension() == ""


# ─────────────────────────────────────────────
# 4. CONFIGURATION PATHS
# ─────────────────────────────────────────────

class TestConfigurationPaths:
    def test_config_base_dir_is_absolute(self):
        from core.config import config
        assert os.path.isabs(config.BASE_DIR)

    def test_config_data_dir_is_absolute(self):
        from core.config import config
        assert os.path.isabs(config.DATA_DIR)

    def test_config_logs_dir_is_absolute(self):
        from core.config import config
        assert os.path.isabs(config.LOGS_DIR)

    def test_config_memory_dir_is_absolute(self):
        from core.config import config
        assert os.path.isabs(config.MEMORY_DIR)

    def test_config_artifacts_dir_is_absolute(self):
        from core.config import config
        assert os.path.isabs(config.AGENT_BUS_ARTIFACTS_DIR)

    def test_config_recovery_journal_is_absolute(self):
        from core.config import config
        assert os.path.isabs(config.RECOVERY_JOURNAL_PATH)

    def test_config_paths_no_cwd_relative(self):
        """
        Verify that no key config paths are bare relative strings
        that would resolve differently depending on CWD.
        """
        from core.config import config
        relative_paths = []
        for attr in ["DATA_DIR", "LOGS_DIR", "MEMORY_DIR",
                     "AGENT_BUS_ARTIFACTS_DIR", "RECOVERY_JOURNAL_PATH"]:
            val = getattr(config, attr)
            if not os.path.isabs(val):
                relative_paths.append(f"{attr}={val}")
        assert not relative_paths, (
            f"These config paths are not absolute: {relative_paths}"
        )

    def test_config_get_data_path_returns_absolute(self):
        from core.config import config
        path = config.get_data_path("test.json")
        assert os.path.isabs(path)

    def test_config_no_hardcoded_username(self):
        """No config path should contain a hardcoded username."""
        from core.config import config
        import getpass
        # The path CAN contain the current user's name (via expanduser)
        # but it must NOT contain 'AZEEZ' as a hardcoded literal
        for attr in ["DATA_DIR", "LOGS_DIR", "MEMORY_DIR",
                     "AGENT_BUS_ARTIFACTS_DIR", "RECOVERY_JOURNAL_PATH"]:
            val = getattr(config, attr)
            # Check for a known hardcoded username from old code
            assert "AZEEZ" not in val, (
                f"{attr} contains hardcoded username 'AZEEZ': {val}"
            )


# ─────────────────────────────────────────────
# 5. PROCESS ABSTRACTION
# ─────────────────────────────────────────────

class TestProcessAbstraction:
    def test_psutil_process_iter_works(self):
        """psutil.process_iter should work on all platforms."""
        import psutil
        procs = list(psutil.process_iter(["pid", "name"]))
        assert len(procs) > 0

    def test_is_running_false_for_nonexistent(self):
        from skills.app_control import is_running
        result = is_running("ultron_nonexistent_process_xyz_12345")
        assert result is False

    def test_is_running_returns_bool(self):
        from skills.app_control import is_running
        result = is_running("python")
        assert isinstance(result, bool)


# ─────────────────────────────────────────────
# 6. APPLICATION ABSTRACTION
# ─────────────────────────────────────────────

class TestApplicationAbstraction:
    def test_open_app_missing_name_returns_string(self):
        from skills.app_control import open_app
        result = open_app("_ultron_nonexistent_app_xyz_")
        assert isinstance(result, str)
        assert "don't know" in result.lower() or "not found" in result.lower()

    def test_close_app_not_running_returns_string(self):
        from skills.app_control import close_app
        result = close_app("_ultron_nonexistent_app_xyz_")
        assert isinstance(result, str)
        assert "not running" in result.lower()

    def test_find_app_returns_none_for_unknown(self):
        from skills.app_control import find_app
        result = find_app("_ultron_nonexistent_app_xyz_")
        assert result is None

    def test_focus_app_returns_bool_or_false(self):
        """focus_app should return bool — False if not found or unavailable."""
        from skills.app_control import focus_app
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.focus_window.return_value = {"available": True, "result": False}
            mock_factory.return_value = mock_adapter
            result = focus_app("nonexistent_window")
            assert isinstance(result, bool)

    def test_adapter_open_application_nonexistent_path(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        result = adapter.open_application("/nonexistent/path/to/executable")
        assert "available" in result
        # Should not raise; should report error gracefully
        assert result.get("error") or result.get("result") is None

    def test_app_search_locations_are_directories(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        locs = adapter.get_app_search_locations()
        for loc in locs:
            assert os.path.isdir(loc), f"App search location is not a directory: {loc}"


# ─────────────────────────────────────────────
# 7. SYSTEM INFORMATION
# ─────────────────────────────────────────────

class TestSystemInformation:
    def test_get_time_returns_string(self):
        from skills.system_control import get_time
        result = get_time()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_date_returns_string(self):
        from skills.system_control import get_date
        result = get_date()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_battery_returns_string(self):
        from skills.system_control import get_battery
        result = get_battery()
        assert isinstance(result, str)

    def test_system_status_returns_string(self):
        from skills.system_control import system_status
        result = system_status()
        assert isinstance(result, str)


# ─────────────────────────────────────────────
# 8. FILESYSTEM OPERATIONS
# ─────────────────────────────────────────────

class TestFilesystemOperations:
    def test_open_downloads_returns_string(self):
        from skills.file_manager import open_downloads
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.open_path.return_value = {"available": True, "result": "Opening Downloads."}
            mock_factory.return_value = mock_adapter
            result = open_downloads()
            assert isinstance(result, str)

    def test_open_desktop_returns_string(self):
        from skills.file_manager import open_desktop
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.open_path.return_value = {"available": True, "result": "Opening Desktop."}
            mock_factory.return_value = mock_adapter
            result = open_desktop()
            assert isinstance(result, str)

    def test_open_documents_returns_string(self):
        from skills.file_manager import open_documents
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.open_path.return_value = {"available": True, "result": "Opening Documents."}
            mock_factory.return_value = mock_adapter
            result = open_documents()
            assert isinstance(result, str)

    def test_search_item_not_found(self):
        from skills.search_files import search_item
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.get_search_locations.return_value = []
            mock_factory.return_value = mock_adapter
            result = search_item("_ultron_nonexistent_file_xyz_12345.txt")
            assert isinstance(result, str)
            assert "couldn't find" in result.lower()

    @skip_windows_only
    def test_open_d_drive_windows(self):
        from skills.file_manager import open_d_drive
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.open_path.return_value = {"available": True, "result": "Opening D drive."}
            mock_factory.return_value = mock_adapter
            result = open_d_drive()
            assert isinstance(result, str)

    @skip_linux_only
    def test_open_d_drive_linux_returns_unavailable(self):
        from skills.file_manager import open_d_drive
        result = open_d_drive()
        assert isinstance(result, str)
        # Must explain that this is Windows-specific — NOT raise an exception
        assert "windows" in result.lower() or "not available" in result.lower()


# ─────────────────────────────────────────────
# 9. SHELL ABSTRACTION
# ─────────────────────────────────────────────

class TestShellAbstraction:
    def test_terminal_command_is_list(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        cmd = adapter.get_terminal_command()
        assert isinstance(cmd, list)
        assert len(cmd) > 0

    def test_terminal_command_first_element_is_string(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        cmd = adapter.get_terminal_command()
        assert isinstance(cmd[0], str)

    @skip_windows_only
    def test_windows_terminal_command_contains_powershell_or_cmd(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        cmd = adapter.get_terminal_command()
        combined = " ".join(cmd).lower()
        assert "powershell" in combined or "cmd" in combined


# ─────────────────────────────────────────────
# 10. PERMISSION HANDLING
# ─────────────────────────────────────────────

class TestPermissionHandling:
    def test_volume_up_returns_string_not_exception(self):
        from skills.volume_control import volume_up
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.volume_up.return_value = {"available": True, "result": "Volume increased Boss."}
            mock_factory.return_value = mock_adapter
            result = volume_up()
            assert isinstance(result, str)

    def test_volume_down_returns_string_not_exception(self):
        from skills.volume_control import volume_down
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.volume_down.return_value = {"available": True, "result": "Volume decreased Boss."}
            mock_factory.return_value = mock_adapter
            result = volume_down()
            assert isinstance(result, str)

    def test_mute_returns_string_not_exception(self):
        from skills.volume_control import mute
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.mute.return_value = {"available": True, "result": "Volume muted Boss."}
            mock_factory.return_value = mock_adapter
            result = mute()
            assert isinstance(result, str)


# ─────────────────────────────────────────────
# 11. UNSUPPORTED CAPABILITY HANDLING
# ─────────────────────────────────────────────

class TestUnsupportedCapabilityHandling:
    """
    Verify that unavailable capabilities return honest status
    rather than raising exceptions or faking success.
    """

    def test_unavailable_volume_returns_message_not_exception(self):
        from skills.volume_control import volume_up
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.volume_up.return_value = {
                "available": False,
                "reason": "No audio control utility found."
            }
            mock_factory.return_value = mock_adapter
            result = volume_up()
            assert isinstance(result, str)
            assert "cannot" in result.lower() or "unavailable" in result.lower()

    def test_unavailable_lock_returns_message_not_exception(self):
        from skills.windows_control import lock_pc
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.lock.return_value = {
                "available": False,
                "reason": "No session lock utility found."
            }
            mock_factory.return_value = mock_adapter
            result = lock_pc()
            assert isinstance(result, str)
            assert "blocked" in result.lower() or "cannot" in result.lower()

    def test_unavailable_focus_returns_false_not_exception(self):
        from skills.app_control import focus_app
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.focus_window.return_value = {
                "available": False,
                "reason": "wmctrl not found."
            }
            mock_factory.return_value = mock_adapter
            result = focus_app("some_app")
            assert result is False  # Graceful degradation

    def test_unavailable_open_path_returns_message(self):
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.open_path.return_value = {
                "available": False,
                "reason": "xdg-open not found."
            }
            mock_factory.return_value = mock_adapter
            from skills.file_manager import open_downloads
            result = open_downloads()
            assert isinstance(result, str)
            assert "cannot" in result.lower()

    def test_linux_adapter_no_audio_returns_unavailable(self):
        """LinuxAdapter with no audio tools must report unavailable."""
        from ultron_platform.linux_adapter import LinuxAdapter
        adapter = LinuxAdapter()
        adapter._audio_backend = "none"
        result = adapter.volume_up()
        assert result.get("available") is False
        assert "reason" in result

    def test_platform_capability_error_importable(self):
        from ultron_platform.interface import PlatformCapabilityError
        err = PlatformCapabilityError("test")
        assert isinstance(err, Exception)


# ─────────────────────────────────────────────
# 12. AGENT INITIALIZATION
# ─────────────────────────────────────────────

class TestAgentInitialization:
    def test_system_agent_imports(self):
        from agents.system_agent import SystemAgent
        assert SystemAgent is not None

    def test_system_agent_instantiates(self):
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        assert agent is not None
        assert agent.agent_id == "system_agent"

    def test_memory_agent_imports(self):
        from agents.memory_agent import MemoryAgent
        assert MemoryAgent is not None

    def test_background_task_agent_imports(self):
        from agents.background_task_agent import BackgroundTaskAgent
        assert BackgroundTaskAgent is not None

    def test_planning_agent_imports(self):
        from agents.planning_agent import PlanningAgent
        assert PlanningAgent is not None

    def test_base_ultron_agent_imports(self):
        from agents.base_ultron_agent import BaseUltronAgent
        assert BaseUltronAgent is not None

    def test_platform_module_importable_from_agent_context(self):
        """Verify platform module can be imported in agent initialization context."""
        from ultron_platform import get_platform_adapter, is_windows, is_linux, platform_name
        assert callable(get_platform_adapter)
        assert callable(is_windows)
        assert callable(is_linux)


# ─────────────────────────────────────────────
# 13. AGENT MANAGER INTEGRATION
# ─────────────────────────────────────────────

class TestAgentManagerIntegration:
    def test_agent_manager_imports(self):
        from brain.agent_manager import AgentManager
        assert AgentManager is not None

    def test_agent_manager_instantiates(self):
        from brain.agent_manager import AgentManager
        mgr = AgentManager()
        assert mgr is not None

    def test_system_agent_registers_with_manager(self):
        from brain.agent_manager import AgentManager
        from agents.system_agent import SystemAgent
        mgr = AgentManager()
        agent = SystemAgent()
        # Should not raise on registration
        mgr.register_agent(agent)
        registered = mgr.get_agent("system_agent")
        assert registered is agent


# ─────────────────────────────────────────────
# 14. MEMORY AGENT INTEGRATION
# ─────────────────────────────────────────────

class TestMemoryAgentIntegration:
    def test_memory_agent_instantiates_no_bus(self):
        from agents.memory_agent import MemoryAgent
        agent = MemoryAgent()
        assert agent.agent_id == "memory_agent"

    def test_memory_agent_health_check(self):
        from agents.memory_agent import MemoryAgent
        agent = MemoryAgent()
        agent.initialize()
        hc = agent.health_check()
        assert "status" in hc
        assert "healthy" in hc
        agent.shutdown()

    def test_memory_agent_execute_task_store_recall(self):
        from agents.memory_agent import MemoryAgent
        agent = MemoryAgent()
        agent.initialize()
        task_id = "cross_platform_mem_test_001"
        result = agent.execute_task(task_id, {"action": "store", "key": "cp_test_key", "value": "cp_test_value"})
        assert result["status"] == "SUCCESS"
        result2 = agent.execute_task(task_id, {"action": "recall", "key": "cp_test_key"})
        assert result2["status"] == "SUCCESS"
        agent.shutdown()


# ─────────────────────────────────────────────
# 15. SYSTEM AGENT INTEGRATION
# ─────────────────────────────────────────────

class TestSystemAgentIntegration:
    def test_system_agent_get_time(self):
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_sys_001", {"action": "get_time"})
        assert result["status"] == "SUCCESS"
        assert isinstance(result["result"], str)
        agent.shutdown()

    def test_system_agent_get_date(self):
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_sys_002", {"action": "get_date"})
        assert result["status"] == "SUCCESS"
        agent.shutdown()

    def test_system_agent_get_battery(self):
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_sys_003", {"action": "get_battery"})
        assert result["status"] == "SUCCESS"
        agent.shutdown()

    def test_system_agent_system_status(self):
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_sys_004", {"action": "system_status"})
        assert result["status"] == "SUCCESS"
        agent.shutdown()

    def test_system_agent_volume_up_via_mock(self):
        """Volume up via system agent — adapter mocked to avoid real audio."""
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.volume_up.return_value = {"available": True, "result": "Volume increased Boss."}
            mock_factory.return_value = mock_adapter
            result = agent.execute_task("cp_sys_005", {"action": "volume_up"})
        assert result["status"] == "SUCCESS"
        agent.shutdown()

    def test_system_agent_lock_via_mock(self):
        """Lock PC via system agent — adapter mocked to avoid actual lock."""
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.lock.return_value = {"available": True, "result": "Locking computer Boss."}
            mock_factory.return_value = mock_adapter
            result = agent.execute_task("cp_sys_006", {"action": "lock_pc"})
        assert result["status"] == "SUCCESS"
        agent.shutdown()

    def test_system_agent_unknown_action_raises(self):
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_sys_007", {"action": "unknown_invalid_action_xyz"})
        assert result["status"] == "ERROR"
        agent.shutdown()


# ─────────────────────────────────────────────
# 16. BACKGROUND TASK AGENT INTEGRATION
# ─────────────────────────────────────────────

class TestBackgroundTaskAgentIntegration:
    def test_background_agent_instantiates(self):
        from agents.background_task_agent import BackgroundTaskAgent
        agent = BackgroundTaskAgent()
        assert agent.agent_id == "background_task_agent"

    def test_background_agent_lifecycle(self):
        from agents.background_task_agent import BackgroundTaskAgent
        agent = BackgroundTaskAgent()
        agent.initialize()
        hc = agent.health_check()
        assert hc["healthy"] is True
        agent.shutdown()
        hc2 = agent.health_check()
        assert hc2["status"] == "OFFLINE"

    def test_background_agent_creates_task(self):
        from agents.background_task_agent import BackgroundTaskAgent
        agent = BackgroundTaskAgent()
        agent.initialize()
        result = agent.execute_task("cp_bg_001", {
            "action": "create_task",
            "task_name": "cross_platform_test_task",
            "description": "Test background task creation in cross-platform suite",
        })
        assert result["status"] == "SUCCESS"
        agent.shutdown()


# ─────────────────────────────────────────────
# 17. PLANNING AGENT INTEGRATION
# ─────────────────────────────────────────────

class TestPlanningAgentIntegration:
    def test_planning_agent_instantiates(self):
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        assert agent.agent_id == "planning_agent"

    def test_planning_agent_lifecycle(self):
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        agent.initialize()
        hc = agent.health_check()
        assert hc["healthy"] is True
        agent.shutdown()

    def test_planning_agent_create_plan(self):
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        agent.initialize()
        result = agent.execute_task("cp_plan_001", {
            "action": "create_plan",
            "goal": "Cross-platform compatibility verification",
            "steps": [
                {"name": "audit", "description": "Audit platform-specific code"},
                {"name": "adapt", "description": "Apply platform adapters"},
            ]
        })
        assert result["status"] == "SUCCESS"
        agent.shutdown()


# ─────────────────────────────────────────────
# 18. SHUTDOWN / CLEANUP
# ─────────────────────────────────────────────

class TestShutdownAndCleanup:
    def test_agent_shutdown_idempotent(self):
        """Calling shutdown twice must not raise."""
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        agent.shutdown()
        agent.shutdown()  # Second call must be safe

    def test_agent_initialize_idempotent(self):
        """Calling initialize twice must not raise."""
        from agents.memory_agent import MemoryAgent
        agent = MemoryAgent()
        agent.initialize()
        agent.initialize()  # Second call must be safe
        agent.shutdown()

    def test_shutdown_pc_blocked_without_token(self):
        """shutdown_pc() must always be blocked without a valid session token."""
        from skills.windows_control import shutdown_pc
        from core.session import session
        session.pending_confirmation = None
        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_factory.return_value = mock_adapter
            result = shutdown_pc()
        assert "security block" in result.lower()
        # The adapter's shutdown() must NOT have been called
        mock_adapter.shutdown.assert_not_called()

    def test_restart_pc_no_actual_restart(self):
        """restart_pc() via mock — must call adapter.restart, not execute real OS restart."""
        from skills.windows_control import restart_pc
        from core.session import session
        import time
        session.pending_confirmation = {
            "action": "restart_pc",
            "validated": True,
            "confirmed": True,
            "created_at": time.time(),
        }
        with patch("ultron_platform.get_platform_adapter") as mock_factory, patch("core.config.config.SAFE_PHYSICAL_TEST_MODE", False):
            mock_adapter = MagicMock()
            mock_adapter.restart.return_value = {"available": True, "result": "Restarting computer Boss."}
            mock_factory.return_value = mock_adapter
            result = restart_pc()
        assert isinstance(result, str)
        mock_adapter.restart.assert_called_once()


# ─────────────────────────────────────────────
# 19. ERROR HANDLING
# ─────────────────────────────────────────────

class TestErrorHandling:
    def test_open_application_nonexistent_path_no_exception(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        result = adapter.open_application("/this/path/does/not/exist/app.exe")
        # Must return dict, not raise
        assert isinstance(result, dict)
        assert "available" in result

    def test_open_path_nonexistent_no_exception(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        # Even for nonexistent path, must not raise
        try:
            result = adapter.open_path("/nonexistent_path_xyz")
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(f"open_path raised exception for nonexistent path: {exc}")

    def test_focus_window_no_match_no_exception(self):
        from ultron_platform import get_platform_adapter
        adapter = get_platform_adapter()
        try:
            result = adapter.focus_window("_nonexistent_window_xyz_12345_")
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(f"focus_window raised exception: {exc}")

    def test_linux_adapter_volume_no_backend_no_exception(self):
        from ultron_platform.linux_adapter import LinuxAdapter
        adapter = LinuxAdapter()
        adapter._audio_backend = "none"
        for method in [adapter.volume_up, adapter.volume_down, adapter.mute,
                       adapter.unmute]:
            try:
                result = method()
                assert isinstance(result, dict)
            except Exception as exc:
                pytest.fail(f"{method.__name__} raised: {exc}")

    def test_system_agent_handles_missing_action(self):
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_err_001", {})  # No action
        assert result["status"] == "ERROR"
        agent.shutdown()

    def test_system_agent_handles_non_dict_payload(self):
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_err_002", "get_time")
        assert result["status"] == "SUCCESS"
        agent.shutdown()


# ─────────────────────────────────────────────
# 20. SECURITY CONTROLS
# ─────────────────────────────────────────────

class TestSecurityControls:
    def test_shutdown_blocked_no_token(self):
        from skills.windows_control import shutdown_pc
        from core.session import session
        session.pending_confirmation = None
        with patch("ultron_platform.get_platform_adapter"):
            result = shutdown_pc()
        assert "security block" in result.lower()

    def test_shutdown_blocked_wrong_action(self):
        """Token with wrong action must be rejected."""
        from skills.windows_control import shutdown_pc
        from core.session import session
        import time
        session.pending_confirmation = {
            "action": "restart_pc",  # Wrong action
            "validated": True,
            "confirmed": True,
            "created_at": time.time(),
        }
        with patch("ultron_platform.get_platform_adapter"):
            result = shutdown_pc()
        assert "security block" in result.lower()
        session.pending_confirmation = None

    def test_shutdown_blocked_expired_token(self):
        """Expired token must be rejected."""
        from skills.windows_control import shutdown_pc
        from core.session import session
        import time
        session.pending_confirmation = {
            "action": "shutdown_pc",
            "validated": True,
            "confirmed": True,
            "created_at": time.time() - 60.0,  # 60s ago — expired
        }
        with patch("ultron_platform.get_platform_adapter"):
            result = shutdown_pc()
        assert "security block" in result.lower()
        session.pending_confirmation = None

    def test_shutdown_blocked_unvalidated_token(self):
        """Token with validated=False must be rejected."""
        from skills.windows_control import shutdown_pc
        from core.session import session
        import time
        session.pending_confirmation = {
            "action": "shutdown_pc",
            "validated": False,
            "confirmed": False,
            "created_at": time.time(),
        }
        with patch("ultron_platform.get_platform_adapter"):
            result = shutdown_pc()
        assert "security block" in result.lower()
        session.pending_confirmation = None

    def test_shutdown_token_cleared_before_execution(self):
        """
        Valid token must be cleared BEFORE the OS command is issued.
        This verifies replay protection is intact.
        """
        from skills.windows_control import shutdown_pc
        from core.session import session
        import time

        session.pending_confirmation = {
            "action": "shutdown_pc",
            "validated": True,
            "confirmed": True,
            "created_at": time.time(),
        }

        with patch("ultron_platform.get_platform_adapter") as mock_factory:
            cleared_before_exec = []

            def mock_shutdown(delay_sec=5):
                # Capture whether token was already cleared
                cleared_before_exec.append(session.pending_confirmation is None)
                return {"available": True, "result": "Shutting down computer Boss."}

            mock_adapter = MagicMock()
            mock_adapter.shutdown.side_effect = mock_shutdown
            mock_factory.return_value = mock_adapter
            with patch("core.config.config.SAFE_PHYSICAL_TEST_MODE", False):
                result = shutdown_pc()

        assert "shutting down" in result.lower() or "safe physical test mode" in result.lower()
        assert cleared_before_exec == [True], (
            "Replay protection VIOLATED: token was not cleared before OS command execution."
        )

    def test_delete_file_blocked_without_confirmed(self):
        """SystemAgent must block delete_file without confirmed=True."""
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_sec_001", {
            "action": "delete_file",
            "path": "/some/file.txt",
            # confirmed not provided — should be blocked
        })
        assert result["status"] == "SUCCESS"
        assert "security block" in str(result["result"]).lower()
        agent.shutdown()

    def test_force_terminate_requires_confirmed(self):
        """SystemAgent must block forced process termination without confirmed=True."""
        from agents.system_agent import SystemAgent
        agent = SystemAgent()
        agent.initialize()
        result = agent.execute_task("cp_sec_002", {
            "action": "close_app",
            "app_name": "notepad",
            "force": True,
            # confirmed not provided
        })
        assert result["status"] == "SUCCESS"
        assert "security block" in str(result["result"]).lower()
        agent.shutdown()

    def test_linux_adapter_no_shell_true(self):
        """
        LinuxAdapter must not use shell=True in any subprocess call.
        This is verified by inspecting that _run_silent uses a list, not a string.
        """
        import inspect
        from ultron_platform import linux_adapter
        source = inspect.getsource(linux_adapter)
        # Filter out comment lines — only code lines must not contain shell=True
        code_lines = [
            line for line in source.splitlines()
            if not line.lstrip().startswith("#") and not line.lstrip().startswith('"""') and not line.lstrip().startswith("'''")
        ]
        code_source = "\n".join(code_lines)
        assert "shell=True" not in code_source, (
            "LinuxAdapter contains shell=True in executable code — this is a security violation."
        )

    def test_windows_adapter_no_shell_true(self):
        """WindowsAdapter must not use shell=True."""
        import inspect
        from ultron_platform import windows_adapter
        source = inspect.getsource(windows_adapter)
        assert "shell=True" not in source, (
            "WindowsAdapter contains shell=True — this is a security violation."
        )
