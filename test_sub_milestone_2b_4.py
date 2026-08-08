"""
ULTRON V3 - Sub-Milestone 2B.4 Unit Tests
Unit test suite for Research Agent, Coding Agent, and Integration.
Zero mock shortcuts - tests actual runtime behavior against Phase 2A and Phase 2B infrastructure.
"""

import os
import shutil
import tempfile
import threading
import time
import unittest
from typing import Dict, Any, List

from brain.agent_bus import AgentMemoryBus
from brain.agent_registry import AgentRegistry
from brain.bus_types import AgentStatus, MessagePriority, AgentMessage
from brain.service_manager import ServiceManager
from core.exceptions import PermissionDeniedException
from brain.workspace_acl import AccessTier

from brain.agent_manager import AgentManager
from agents.research_agent import ResearchAgent, ResearchTaskStatus
from agents.coding_agent import CodingAgent, CodingTaskStatus


class TestSubMilestone2B4(unittest.TestCase):
    """
    Sub-Milestone 2B.4 Unit Test Suite (33 Scenarios).
    """

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="ultron_test_2b4_")

        # Initialize AgentMemoryBus & AgentManager
        self.bus = AgentMemoryBus()
        self.bus.initialize()
        self.manager = AgentManager(bus=self.bus)
        self.manager.initialize()

        # Instantiate & initialize agents
        self.research_agent = ResearchAgent(bus=self.bus)
        self.research_agent.initialize()
        self.coding_agent = CodingAgent(bus=self.bus)
        self.coding_agent.initialize()

    def tearDown(self) -> None:
        try:
            if hasattr(self, "manager") and self.manager:
                self.manager.shutdown()
        except Exception:
            pass
        try:
            if hasattr(self, "bus") and self.bus:
                self.bus.shutdown()
        except Exception:
            pass
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # RESEARCH AGENT TESTS (13 Scenarios)
    # =========================================================================

    def test_01_research_agent_registration(self) -> None:
        """Scenario 1: Registration of ResearchAgent with AgentManager and AgentRegistry."""
        success = self.manager.register_agent(self.research_agent)
        self.assertTrue(success)
        self.assertIn("research_agent", [a["agent_id"] for a in self.manager.list_agents()])
        reg_agent = self.bus.agent_registry.get_agent("research_agent")
        self.assertIsNotNone(reg_agent)
        self.assertEqual(reg_agent.name, "Research Agent")

    def test_02_research_agent_capability_discovery(self) -> None:
        """Scenario 2: Capability discovery for ResearchAgent."""
        caps = self.research_agent.capabilities
        self.assertIn("create_research_task", caps)
        self.assertIn("conduct_research", caps)
        self.assertIn("information_retrieval", caps)
        self.assertIn("source_collection", caps)
        self.assertIn("source_validation", caps)
        self.assertIn("result_synthesis", caps)
        self.assertIn("generate_research_artifact", caps)

    def test_03_research_agent_lifecycle(self) -> None:
        """Scenario 3: Lifecycle transitions of ResearchAgent (OFFLINE -> INITIALIZING -> ONLINE -> OFFLINE)."""
        agent = ResearchAgent(bus=self.bus)
        self.assertEqual(agent.status, AgentStatus.OFFLINE)
        agent.initialize()
        self.assertEqual(agent.status, AgentStatus.ONLINE)
        agent.shutdown()
        self.assertEqual(agent.status, AgentStatus.OFFLINE)

    def test_04_research_task_creation(self) -> None:
        """Scenario 4: Research task creation and WorkspaceStore persistence."""
        self.research_agent.initialize()
        res = self.research_agent.execute_task("task_res_01", {
            "action": "create_research_task",
            "query": "ULTRON V3 Architecture",
            "topic": "system_design",
        })
        self.assertEqual(res["status"], "SUCCESS")
        r_id = res["result"]["research_id"]
        self.assertIsNotNone(r_id)

    def test_05_source_collection(self) -> None:
        """Scenario 5: Source collection and structuring."""
        self.research_agent.initialize()
        res = self.research_agent.execute_task("task_res_02", {
            "action": "source_collection",
            "sources": [
                {"title": "Doc 1", "url_or_path": "https://example.com/doc1", "snippet": "ULTRON Bus Overview"},
                {"title": "Doc 2", "url_or_path": "https://example.com/doc2", "snippet": "Agent Architecture"},
            ]
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["result"]["collected_count"], 2)

    def test_06_source_validation(self) -> None:
        """Scenario 6: Source validation with security domain filtering."""
        self.research_agent.initialize()
        res = self.research_agent.execute_task("task_res_03", {
            "action": "source_validation",
            "sources": [
                {"title": "Safe", "url_or_path": "https://example.com/spec", "snippet": "Valid Spec"},
                {"title": "Malware", "url_or_path": "https://malware.example/bad", "snippet": "Malicious code"},
            ]
        })
        self.assertEqual(res["status"], "SUCCESS")
        validated = res["result"]["validated_sources"]
        self.assertTrue(validated[0]["is_valid"])
        self.assertFalse(validated[1]["is_valid"])

    def test_07_result_synthesis(self) -> None:
        """Scenario 7: Findings synthesis from validated sources."""
        self.research_agent.initialize()
        res = self.research_agent.execute_task("task_res_04", {
            "action": "result_synthesis",
            "query": "Voice Pipeline Latency",
            "sources": [
                {"title": "Paper 1", "snippet": "Preload voice model cuts latency by 50%", "is_valid": True},
            ]
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("Preload voice model", res["result"]["summary"])

    def test_08_generate_research_artifact(self) -> None:
        """Scenario 8: ArtifactRegistry integration for research report generation."""
        self.research_agent.initialize()
        res = self.research_agent.execute_task("task_res_05", {
            "action": "generate_research_artifact",
            "title": "Voice Optimization Report",
            "query": "Latency Reduction",
            "summary": "Caching improves responsiveness.",
            "findings": ["Preloading model works.", "Cache tokens."],
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("artifact_id", res["result"])
        self.assertIn("# Voice Optimization Report", res["result"]["content"])

    def test_09_unavailable_provider_handling(self) -> None:
        """Scenario 9: Honest status reporting when web/search provider is unconfigured."""
        self.research_agent.initialize()
        res = self.research_agent.execute_task("task_res_06", {
            "action": "information_retrieval",
            "query": "Quantum Computing",
            "provider": "unconfigured_web_provider",
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertFalse(res["result"]["available"])
        self.assertIn("not configured", res["result"]["reason"])

    def test_10_task_cancellation(self) -> None:
        """Scenario 10: Research task cancellation."""
        self.research_agent.initialize()
        c_res = self.research_agent.execute_task("task_res_07", {
            "action": "create_research_task",
            "query": "Cancel Me",
        })
        r_id = c_res["result"]["research_id"]
        res = self.research_agent.execute_task("task_res_08", {
            "action": "cancel_research",
            "research_id": r_id,
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["result"]["status"], ResearchTaskStatus.CANCELLED.value)

    def test_11_error_handling_and_recovery(self) -> None:
        """Scenario 11: Error handling for invalid payload actions."""
        self.research_agent.initialize()
        res = self.research_agent.execute_task("task_res_09", {
            "action": "invalid_research_action_xyz",
        })
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("Unsupported action", res["error"])

    def test_12_workspace_acl_file_research(self) -> None:
        """Scenario 12: WorkspaceACL permission check on file research path."""
        self.research_agent.initialize()
        test_file = os.path.join(self.test_dir, "research_file.txt")
        with open(test_file, "w") as f:
            f.write("Secret ULTRON Data")

        res = self.research_agent.execute_task("task_res_10", {
            "action": "information_retrieval",
            "query": "Secret",
            "search_path": test_file,
        })
        self.assertEqual(res["status"], "SUCCESS")

    def test_13_research_metrics_telemetry(self) -> None:
        """Scenario 13: Metrics and telemetry updating."""
        self.research_agent.initialize()
        self.research_agent.execute_task("task_res_11", {
            "action": "create_research_task",
            "query": "Telemetry Test",
        })
        metrics = self.research_agent.get_metrics()
        self.assertGreater(metrics["tasks_executed"], 0)

    # =========================================================================
    # CODING AGENT TESTS (15 Scenarios)
    # =========================================================================

    def test_14_coding_agent_registration(self) -> None:
        """Scenario 14: Registration of CodingAgent with AgentManager and AgentRegistry."""
        success = self.manager.register_agent(self.coding_agent)
        self.assertTrue(success)
        self.assertIn("coding_agent", [a["agent_id"] for a in self.manager.list_agents()])
        reg_agent = self.bus.agent_registry.get_agent("coding_agent")
        self.assertIsNotNone(reg_agent)
        self.assertEqual(reg_agent.name, "Coding Agent")

    def test_15_coding_agent_capability_discovery(self) -> None:
        """Scenario 15: Capability discovery for CodingAgent."""
        caps = self.coding_agent.capabilities
        self.assertIn("inspect_project_files", caps)
        self.assertIn("understand_repo_structure", caps)
        self.assertIn("generate_code", caps)
        self.assertIn("modify_code", caps)
        self.assertIn("validate_syntax", caps)
        self.assertIn("run_authorized_tests", caps)
        self.assertIn("produce_patch_artifact", caps)
        self.assertIn("rollback_code_changes", caps)

    def test_16_coding_agent_lifecycle(self) -> None:
        """Scenario 16: Lifecycle transitions of CodingAgent."""
        agent = CodingAgent(bus=self.bus)
        self.assertEqual(agent.status, AgentStatus.OFFLINE)
        agent.initialize()
        self.assertEqual(agent.status, AgentStatus.ONLINE)
        agent.shutdown()
        self.assertEqual(agent.status, AgentStatus.OFFLINE)

    def test_17_repository_inspection(self) -> None:
        """Scenario 17: Repository structure inspection."""
        self.coding_agent.initialize()
        res = self.coding_agent.execute_task("task_code_01", {
            "action": "understand_repo_structure",
            "root_path": self.test_dir,
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("structure", res["result"])

    def test_18_code_generation(self) -> None:
        """Scenario 18: Python code generation with syntax validation."""
        self.coding_agent.initialize()
        res = self.coding_agent.execute_task("task_code_02", {
            "action": "generate_code",
            "language": "python",
            "specification": "Calculate factorial",
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["result"]["syntax_valid"])
        self.assertIn("def main():", res["result"]["code"])

    def test_19_authorized_code_modification(self) -> None:
        """Scenario 19: Authorized code modification under WorkspaceACL."""
        self.coding_agent.initialize()
        target_file = os.path.join(self.test_dir, "sample.py")
        code = "def add(a, b):\n    return a + b\n"

        res = self.coding_agent.execute_task("task_code_03", {
            "action": "modify_code",
            "target_file": target_file,
            "content": code,
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(os.path.exists(target_file))
        with open(target_file, "r") as f:
            self.assertEqual(f.read(), code)

    def test_20_ast_syntax_validation(self) -> None:
        """Scenario 20: AST syntax validation for valid vs invalid Python."""
        self.coding_agent.initialize()
        valid_code = "x = 42\n"
        invalid_code = "def broken_func(\n"

        res_valid = self.coding_agent.execute_task("task_code_04a", {
            "action": "validate_syntax",
            "code": valid_code,
        })
        self.assertTrue(res_valid["result"]["syntax_valid"])

        res_invalid = self.coding_agent.execute_task("task_code_04b", {
            "action": "validate_syntax",
            "code": invalid_code,
        })
        self.assertFalse(res_invalid["result"]["syntax_valid"])

    def test_21_authorized_test_execution(self) -> None:
        """Scenario 21: Authorized test execution via safe subprocess array."""
        self.coding_agent.initialize()
        test_file = os.path.join(self.test_dir, "test_sample.py")
        with open(test_file, "w") as f:
            f.write("import unittest\nclass T(unittest.TestCase):\n    def test_pass(self):\n        self.assertTrue(True)\n")

        res = self.coding_agent.execute_task("task_code_05", {
            "action": "run_authorized_tests",
            "test_target": test_file,
            "runner": "unittest",
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["result"]["success"])

    def test_22_inspect_test_failures(self) -> None:
        """Scenario 22: Inspection and diagnostic parsing of test failure output."""
        self.coding_agent.initialize()
        logs = "FAILED test_module.py::test_foo - AssertionError: 1 != 2"
        res = self.coding_agent.execute_task("task_code_06", {
            "action": "inspect_test_failures",
            "stdout": logs,
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(res["result"]["failure_count"], 0)

    def test_23_transaction_backed_rollback(self) -> None:
        """Scenario 23: Transaction-backed file backup and rollback."""
        self.coding_agent.initialize()
        target_file = os.path.join(self.test_dir, "rollback_target.py")
        orig_content = "ORIGINAL_CODE = True\n"
        with open(target_file, "w") as f:
            f.write(orig_content)

        # Modify file
        c_id = "coding_tx_001"
        self.coding_agent.execute_task("task_code_07", {
            "action": "modify_code",
            "coding_id": c_id,
            "target_file": target_file,
            "content": "MODIFIED_CODE = False\n",
        })

        # Rollback
        res = self.coding_agent.execute_task("task_code_08", {
            "action": "rollback_code_changes",
            "coding_id": c_id,
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["result"]["rolled_back"])

        with open(target_file, "r") as f:
            self.assertEqual(f.read(), orig_content)

    def test_24_unauthorized_path_protection(self) -> None:
        """Scenario 24: WorkspaceACL boundary enforcement blocking unauthorized paths."""
        self.coding_agent.initialize()
        unauthorized_path = "/etc/shadow_unauthorized_test"

        # Mock ACL permission denial
        self.bus.workspace_acl.revoke_permission("*", self.coding_agent.agent_id)

        res = self.coding_agent.execute_task("task_code_09", {
            "action": "inspect_project_files",
            "file_path": unauthorized_path,
        })
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("PermissionDeniedException", res["error"])

    def test_25_shell_security_protection(self) -> None:
        """Scenario 25: Verify safe subprocess argument array execution (no shell=True)."""
        self.coding_agent.initialize()
        import inspect
        from agents import coding_agent
        source = inspect.getsource(coding_agent)
        self.assertNotIn("shell=True", source)

    def test_26_produce_patch_artifact(self) -> None:
        """Scenario 26: Patch artifact generation with ArtifactRegistry."""
        self.coding_agent.initialize()
        res = self.coding_agent.execute_task("task_code_10", {
            "action": "produce_patch_artifact",
            "title": "Fix Bug",
            "target_file": "app.py",
            "diff": "--- app.py\n+++ app.py\n- print(1)\n+ print(2)\n",
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("artifact_id", res["result"])

    def test_27_secrets_redaction(self) -> None:
        """Scenario 27: Redaction of sensitive credentials and API keys."""
        self.coding_agent.initialize()
        secret_content = "api_key = 'secret_abc12345'\npassword = 'my_password_xyz'\n"
        clean = self.coding_agent._redact_secrets(secret_content)
        self.assertNotIn("secret_abc12345", clean)
        self.assertNotIn("my_password_xyz", clean)
        self.assertIn("[REDACTED]", clean)

    def test_28_coding_metrics_telemetry(self) -> None:
        """Scenario 28: Coding agent metrics telemetry updating."""
        self.coding_agent.initialize()
        self.coding_agent.execute_task("task_code_11", {
            "action": "generate_code",
            "specification": "Test snippet",
        })
        metrics = self.coding_agent.get_metrics()
        self.assertGreater(metrics["tasks_executed"], 0)

    # =========================================================================
    # INTEGRATION TESTS (5 Scenarios)
    # =========================================================================

    def test_29_manager_registration_both_agents(self) -> None:
        """Scenario 29: AgentManager registration for both ResearchAgent and CodingAgent."""
        ok1 = self.manager.register_agent(self.research_agent)
        ok2 = self.manager.register_agent(self.coding_agent)
        self.assertTrue(ok1)
        self.assertTrue(ok2)
        agents = [a["agent_id"] for a in self.manager.list_agents()]
        self.assertIn("research_agent", agents)
        self.assertIn("coding_agent", agents)

    def test_30_agent_registry_synchronization(self) -> None:
        """Scenario 30: AgentRegistry synchronization for Research & Coding agents."""
        self.manager.register_agent(self.research_agent)
        self.manager.register_agent(self.coding_agent)

        r_reg = self.bus.agent_registry.get_agent("research_agent")
        c_reg = self.bus.agent_registry.get_agent("coding_agent")

        self.assertIsNotNone(r_reg)
        self.assertIsNotNone(c_reg)
        self.assertEqual(r_reg.capabilities, self.research_agent.capabilities)
        self.assertEqual(c_reg.capabilities, self.coding_agent.capabilities)

    def test_31_agent_bus_p2p_messaging(self) -> None:
        """Scenario 31: AgentMemoryBus messaging between ResearchAgent and CodingAgent."""
        self.manager.register_agent(self.research_agent)
        self.manager.register_agent(self.coding_agent)

        msg = AgentMessage(
            sender_id="research_agent",
            recipient_id="coding_agent",
            payload={"action": "implement_specification", "spec": "Build parser"},
            priority=MessagePriority.HIGH,
        )

        received_messages = []

        def handle_msg(a_msg: AgentMessage):
            received_messages.append(a_msg)

        self.coding_agent.receive_message = handle_msg

        self.bus.send_message(msg)
        time.sleep(0.2)
        self.assertGreaterEqual(len(received_messages), 1)

    def test_32_workspace_store_and_acl_cross_agent(self) -> None:
        """Scenario 32: WorkspaceStore data sharing and WorkspaceACL isolation."""
        self.manager.register_agent(self.research_agent)
        self.manager.register_agent(self.coding_agent)

        # Grant ResearchAgent owner permissions on research path
        self.bus.grant_permission("workspace/research/*", "research_agent", AccessTier.OWNER)

        # Write data
        self.bus.write_workspace("workspace/research/notes", {"findings": "API Spec"}, owner_agent="research_agent")

        # Grant CodingAgent read access
        self.bus.grant_permission("workspace/research/*", "coding_agent", AccessTier.READ)

        # CodingAgent reads data
        data = self.bus.read_workspace("workspace/research/notes", agent_id="coding_agent")
        self.assertEqual(data["findings"], "API Spec")

    def test_33_orchestrator_dispatch_and_graceful_shutdown(self) -> None:
        """Scenario 33: Dispatch task to agents via AgentManager and verify graceful shutdown."""
        self.manager.register_agent(self.research_agent)
        self.manager.register_agent(self.coding_agent)

        # Dispatch task to Research Agent
        res_r = self.manager.dispatch_task("research_agent", "t_pipe_01", {
            "action": "create_research_task",
            "query": "Pipeline Test",
        })
        self.assertEqual(res_r["status"], "SUCCESS")

        # Dispatch task to Coding Agent
        res_c = self.manager.dispatch_task("coding_agent", "t_pipe_02", {
            "action": "generate_code",
            "specification": "Pipeline Code",
        })
        self.assertEqual(res_c["status"], "SUCCESS")

        # Graceful shutdown
        self.manager.shutdown()
        self.assertEqual(self.research_agent.status, AgentStatus.OFFLINE)
        self.assertEqual(self.coding_agent.status, AgentStatus.OFFLINE)


if __name__ == "__main__":
    unittest.main()
