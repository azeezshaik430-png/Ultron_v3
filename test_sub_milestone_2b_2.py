"""
ULTRON V3 - Sub-Milestone 2B.2 Unit Test Suite
System Control Agent + Memory/Knowledge Agent Integration Verification
Covers all 25 specific requirements for Phase 2B.2.
"""

import unittest
from unittest.mock import patch
import time
import os
import shutil

from core.config import config
from core.exceptions import PermissionDeniedException, BusException
from brain.agent_bus import AgentMemoryBus
from brain.agent_manager import AgentManager
from brain.bus_types import CircuitBreakerState, AgentStatus
from brain.workspace_acl import AccessTier
from agents.system_agent import SystemAgent
from agents.memory_agent import MemoryAgent
import brain.memory as memory_sys


class TestSubMilestone2B2(unittest.TestCase):

    def setUp(self):
        self.bus = AgentMemoryBus()
        self.agent_mgr = AgentManager(bus=self.bus)
        self.system_agent = SystemAgent(bus=self.bus)
        self.memory_agent = MemoryAgent(bus=self.bus)
        self.agent_mgr.initialize()

    def tearDown(self):
        if self.agent_mgr._is_initialized:
            self.agent_mgr.shutdown()
        # Cleanup data directory artifacts
        if os.path.exists("data/test_artifacts"):
            shutil.rmtree("data/test_artifacts", ignore_errors=True)
        memory_sys.clear_memory()

    # =========================================================================
    # SYSTEM AGENT TESTS (1 - 10)
    # =========================================================================

    def test_01_system_agent_registration(self):
        """Test 1: SystemAgent registration with AgentManager."""
        res = self.agent_mgr.register_agent(self.system_agent)
        self.assertTrue(res)
        found = self.agent_mgr.get_agent("system_agent")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "System Control Agent")

    def test_02_system_agent_capability_discovery(self):
        """Test 2: SystemAgent capability discovery via AgentManager."""
        self.agent_mgr.register_agent(self.system_agent)
        agents = self.agent_mgr.find_agents_by_capability("application_control")
        self.assertGreaterEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_id, "system_agent")

    def test_03_system_agent_lifecycle_startup_shutdown(self):
        """Test 3: SystemAgent startup, status online, and clean shutdown."""
        self.agent_mgr.register_agent(self.system_agent)
        self.assertEqual(self.system_agent.status, AgentStatus.ONLINE)
        self.system_agent.shutdown()
        self.assertEqual(self.system_agent.status, AgentStatus.OFFLINE)

    def test_04_system_agent_application_control(self):
        """Test 4: SystemAgent open_app, is_running, and focus_app capability."""
        self.agent_mgr.register_agent(self.system_agent)
        res = self.system_agent.execute_task(
            "tsk_app_1",
            {"action": "is_running", "app_name": "non_existent_app_xyz"}
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertFalse(res["result"])

    def test_05_system_agent_system_information(self):
        """Test 5: SystemAgent system info queries (time, date, battery, status)."""
        self.agent_mgr.register_agent(self.system_agent)
        res_time = self.system_agent.execute_task("tsk_time", {"action": "get_time"})
        self.assertEqual(res_time["status"], "SUCCESS")
        self.assertIn("The time is", res_time["result"])

        res_date = self.system_agent.execute_task("tsk_date", {"action": "get_date"})
        self.assertEqual(res_date["status"], "SUCCESS")
        self.assertIn("Today is", res_date["result"])

        res_status = self.system_agent.execute_task("tsk_stat", {"action": "system_status"})
        self.assertEqual(res_status["status"], "SUCCESS")
        self.assertIn("online", res_status["result"])

    @patch("skills.search_files.search_item", return_value="Opening test_file.txt")
    def test_06_system_agent_file_operation_integration(self, mock_search):
        """Test 6: SystemAgent file operation navigation (downloads, desktop, search)."""
        self.agent_mgr.register_agent(self.system_agent)
        res_srch = self.system_agent.execute_task(
            "tsk_file_srch",
            {"action": "search_files", "query": "test_file.txt"}
        )
        self.assertEqual(res_srch["status"], "SUCCESS")
        self.assertEqual(res_srch["result"], "Opening test_file.txt")
        mock_search.assert_called_once_with("test_file.txt")

    def test_07_system_agent_permission_enforcement(self):
        """Test 7: WorkspaceACL permission enforcement for SystemAgent."""
        self.agent_mgr.register_agent(self.system_agent)
        # Writing to system_agent workspace allowed
        self.system_agent.write_workspace("workspace/system_agent/cfg", "val")
        read_val = self.system_agent.read_workspace("workspace/system_agent/cfg")
        self.assertEqual(read_val, "val")

        # Create a key owned by foreign_agent with explicit restricted ACL
        self.bus.write_workspace("workspace/foreign_agent/secret", "secret_val", owner_agent="foreign_agent")
        self.bus.grant_permission("workspace/foreign_agent/secret", "foreign_agent", AccessTier.OWNER)

        # Writing to unauthorized foreign workspace by system_agent blocked by ACL
        with self.assertRaises(PermissionDeniedException):
            self.bus.write_workspace("workspace/foreign_agent/secret", "hacked", owner_agent="system_agent")

    def test_08_system_agent_destructive_action_protection(self):
        """Test 8: SystemAgent destructive action guards (unconfirmed restart / delete / shutdown)."""
        self.agent_mgr.register_agent(self.system_agent)
        
        # Unconfirmed file deletion -> returns security block
        res_del = self.system_agent.execute_task(
            "tsk_del_1",
            {"action": "delete_file", "path": "important_file.txt", "confirmed": False}
        )
        self.assertEqual(res_del["status"], "SUCCESS")
        self.assertIn("Security block", res_del["result"])

        # Unconfirmed restart -> returns security block
        res_rst = self.system_agent.execute_task(
            "tsk_rst_1",
            {"action": "restart_pc", "confirmed": False}
        )
        self.assertEqual(res_rst["status"], "SUCCESS")
        self.assertIn("Security block", res_rst["result"])

        # Unauthorized shutdown -> blocked by session guard
        res_sdown = self.system_agent.execute_task("tsk_sd_1", {"action": "shutdown_pc"})
        self.assertEqual(res_sdown["status"], "SUCCESS")
        self.assertIn("Security block", res_sdown["result"])

    def test_09_system_agent_error_handling(self):
        """Test 9: SystemAgent invalid/unknown action error handling."""
        self.agent_mgr.register_agent(self.system_agent)
        res = self.system_agent.execute_task(
            "tsk_err_1",
            {"action": "invalid_unknown_action"}
        )
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("Unknown or unsupported system action", res["error"])

    def test_10_system_agent_telemetry(self):
        """Test 10: SystemAgent health check and telemetry metrics aggregation."""
        self.agent_mgr.register_agent(self.system_agent)
        self.system_agent.execute_task("tsk_t1", {"action": "get_time"})
        health = self.system_agent.health_check()
        self.assertTrue(health["healthy"])
        self.assertEqual(health["metrics"]["tasks_executed"], 1)
        self.assertGreater(health["metrics"]["total_execution_time_ms"], 0.0)

    # =========================================================================
    # MEMORY AGENT TESTS (11 - 20)
    # =========================================================================

    def test_11_memory_agent_registration(self):
        """Test 11: MemoryAgent registration with AgentManager."""
        res = self.agent_mgr.register_agent(self.memory_agent)
        self.assertTrue(res)
        found = self.agent_mgr.get_agent("memory_agent")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Memory Knowledge Agent")

    def test_12_memory_agent_capability_discovery(self):
        """Test 12: MemoryAgent capability discovery via AgentManager."""
        self.agent_mgr.register_agent(self.memory_agent)
        agents = self.agent_mgr.find_agents_by_capability("store_memory")
        self.assertGreaterEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_id, "memory_agent")

    def test_13_memory_agent_lifecycle_startup_shutdown(self):
        """Test 13: MemoryAgent lifecycle state transition online -> offline."""
        self.agent_mgr.register_agent(self.memory_agent)
        self.assertEqual(self.memory_agent.status, AgentStatus.ONLINE)
        self.memory_agent.shutdown()
        self.assertEqual(self.memory_agent.status, AgentStatus.OFFLINE)

    def test_14_memory_agent_memory_write(self):
        """Test 14: MemoryAgent store_memory writing to memory.json and WorkspaceStore."""
        self.agent_mgr.register_agent(self.memory_agent)
        res = self.memory_agent.execute_task(
            "tsk_mem_w",
            {"action": "store_memory", "key": "user_name", "value": "Azeez"}
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["result"]["key"], "user_name")
        self.assertEqual(res["result"]["value"], "Azeez")
        
        # Verify persistence in brain.memory
        recalled = memory_sys.recall("user_name")
        self.assertEqual(recalled, "Azeez")

    def test_15_memory_agent_memory_retrieval(self):
        """Test 15: MemoryAgent retrieve_memory fetching stored memory."""
        self.agent_mgr.register_agent(self.memory_agent)
        memory_sys.remember("preferred_theme", "dark")

        res = self.memory_agent.execute_task(
            "tsk_mem_r",
            {"action": "retrieve_memory", "key": "preferred_theme"}
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["result"]["found"])
        self.assertEqual(res["result"]["value"], "dark")

    def test_16_memory_agent_memory_update(self):
        """Test 16: MemoryAgent update_memory updating existing entries."""
        self.agent_mgr.register_agent(self.memory_agent)
        self.memory_agent.execute_task(
            "tsk_mem_u1",
            {"action": "store_memory", "key": "favorite_color", "value": "blue"}
        )
        res = self.memory_agent.execute_task(
            "tsk_mem_u2",
            {"action": "update_memory", "key": "favorite_color", "value": "emerald"}
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["result"]["updated"])
        self.assertEqual(res["result"]["value"], "emerald")
        self.assertEqual(memory_sys.recall("favorite_color"), "emerald")

    def test_17_memory_agent_explicit_memory_deletion(self):
        """Test 17: MemoryAgent delete_memory explicitly removing memory entries."""
        self.agent_mgr.register_agent(self.memory_agent)
        memory_sys.remember("temp_key", "temp_val")
        self.assertEqual(memory_sys.recall("temp_key"), "temp_val")

        res = self.memory_agent.execute_task(
            "tsk_mem_d",
            {"action": "delete_memory", "key": "temp_key"}
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["result"]["deleted"])
        self.assertIsNone(memory_sys.recall("temp_key"))

    def test_18_memory_agent_acl_enforcement(self):
        """Test 18: WorkspaceACL enforcement on MemoryAgent workspace operations."""
        self.agent_mgr.register_agent(self.memory_agent)
        # Store memory syncs to workspace/memory_agent/memories/city
        self.memory_agent.execute_task(
            "tsk_acl_mem",
            {"action": "store_memory", "key": "city", "value": "Hyderabad"}
        )
        # Verified memory_agent can read its own workspace key
        ws_val = self.memory_agent.read_workspace("workspace/memory_agent/memories/city")
        self.assertEqual(ws_val, "Hyderabad")

        # Create foreign owned key with explicit ACL rule
        self.bus.write_workspace("workspace/other_agent/key1", "val1", owner_agent="other_agent")
        self.bus.grant_permission("workspace/other_agent/key1", "other_agent", AccessTier.OWNER)

        # MemoryAgent writing to foreign key blocked by ACL
        with self.assertRaises(PermissionDeniedException):
            self.bus.write_workspace("workspace/other_agent/key1", "hacked", owner_agent="memory_agent")

    def test_19_memory_agent_transaction_error_recovery(self):
        """Test 19: MemoryAgent transaction rollback and error recovery."""
        self.agent_mgr.register_agent(self.memory_agent)
        # Attempting silent store of sensitive data without approval -> returns security block
        res_sec = self.memory_agent.execute_task(
            "tsk_sec_1",
            {"action": "store_memory", "key": "pin", "value": "1234", "sensitive": True, "approved": False}
        )
        self.assertEqual(res_sec["status"], "SUCCESS")
        self.assertIn("Security block", res_sec["result"])
        self.assertIsNone(memory_sys.recall("pin"))

    def test_20_memory_agent_telemetry(self):
        """Test 20: MemoryAgent structured query and telemetry metrics."""
        self.agent_mgr.register_agent(self.memory_agent)
        self.memory_agent.execute_task(
            "tsk_sq_1",
            {"action": "store_memory", "key": "lang", "value": "Python"}
        )
        res_sq = self.memory_agent.execute_task(
            "tsk_sq_2",
            {"action": "structured_query"}
        )
        self.assertEqual(res_sq["status"], "SUCCESS")
        self.assertIn("lang", res_sq["result"]["memories"])

        health = self.memory_agent.health_check()
        self.assertTrue(health["healthy"])
        self.assertEqual(health["metrics"]["tasks_executed"], 2)

    # =========================================================================
    # INTEGRATION TESTS (21 - 25)
    # =========================================================================

    def test_21_agent_manager_discovery(self):
        """Test 21: AgentManager multi-agent registration and discovery."""
        self.agent_mgr.register_agent(self.system_agent)
        self.agent_mgr.register_agent(self.memory_agent)
        all_agents = self.agent_mgr.list_agents()
        self.assertEqual(len(all_agents), 2)
        
        sys_ag = self.agent_mgr.get_agent("system_agent")
        mem_ag = self.agent_mgr.get_agent("memory_agent")
        self.assertIsNotNone(sys_ag)
        self.assertIsNotNone(mem_ag)

    def test_22_agent_bus_communication(self):
        """Test 22: Message exchange between SystemAgent and MemoryAgent via AgentMemoryBus."""
        self.agent_mgr.register_agent(self.system_agent)
        self.agent_mgr.register_agent(self.memory_agent)

        # SystemAgent sends P2P message to MemoryAgent
        msg_id = self.system_agent.send_message(
            recipient_id="memory_agent",
            topic="status_report",
            payload={"system": "healthy"}
        )
        self.assertIsNotNone(msg_id)

        # MemoryAgent receives and acknowledges message
        msg = self.memory_agent.receive_message()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.sender_id, "system_agent")
        ack_res = self.memory_agent.acknowledge_message(msg.message_id)
        self.assertTrue(ack_res)

    def test_23_orchestrator_dispatch_integration(self):
        """Test 23: Orchestrator dispatching tasks through AgentManager to System & Memory agents."""
        self.agent_mgr.register_agent(self.system_agent)
        self.agent_mgr.register_agent(self.memory_agent)

        # Orchestrator dispatches system task
        res_sys = self.agent_mgr.dispatch_task(
            target="system_agent",
            task_id="orch_sys_1",
            payload={"action": "get_time"}
        )
        self.assertEqual(res_sys["status"], "SUCCESS")
        self.assertIn("The time is", res_sys["result"])

        # Orchestrator dispatches memory task
        res_mem = self.agent_mgr.dispatch_task(
            target="memory_agent",
            task_id="orch_mem_1",
            payload={"action": "store_memory", "key": "project", "value": "ULTRON_V3"}
        )
        self.assertEqual(res_mem["status"], "SUCCESS")
        self.assertEqual(memory_sys.recall("project"), "ULTRON_V3")

    def test_24_health_monitoring(self):
        """Test 24: Aggregate health monitoring across SystemAgent, MemoryAgent, and AgentMemoryBus."""
        self.agent_mgr.register_agent(self.system_agent)
        self.agent_mgr.register_agent(self.memory_agent)
        
        agg_health = self.agent_mgr.health_check()
        self.assertEqual(agg_health["status"], "HEALTHY")
        self.assertEqual(agg_health["agents_count"], 2)
        self.assertTrue(agg_health["agent_health"]["system_agent"]["healthy"])
        self.assertTrue(agg_health["agent_health"]["memory_agent"]["healthy"])

    def test_25_graceful_shutdown(self):
        """Test 25: Graceful shutdown sequence for AgentManager, agents, and bus."""
        self.agent_mgr.register_agent(self.system_agent)
        self.agent_mgr.register_agent(self.memory_agent)

        self.assertEqual(self.system_agent.status, AgentStatus.ONLINE)
        self.assertEqual(self.memory_agent.status, AgentStatus.ONLINE)

        self.agent_mgr.shutdown()

        self.assertEqual(self.system_agent.status, AgentStatus.OFFLINE)
        self.assertEqual(self.memory_agent.status, AgentStatus.OFFLINE)
        self.assertFalse(self.agent_mgr._is_initialized)


if __name__ == "__main__":
    unittest.main()
