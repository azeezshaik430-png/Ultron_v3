"""
ULTRON V3 - Sub-Milestone 2B.3 Unit Tests
Unit test suite for Background Task Agent, Planning / Reasoning Agent, Plan Models, and System Integration.
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
from brain.bus_types import AgentStatus, MessagePriority
from brain.service_manager import ServiceManager
from core.exceptions import PermissionDeniedException
from brain.workspace_acl import AccessTier

from brain.agent_manager import AgentManager
from agents.background_task_agent import BackgroundTaskAgent
from agents.planning_agent import PlanningAgent, ExecutionPlan, PlanStep, StepStatus, PlanStatus
from core.task_models import TaskStatus, PriorityLevel


class TestSubMilestone2B3(unittest.TestCase):
    """
    Sub-Milestone 2B.3 Unit Test Suite (32 Scenarios).
    """

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="ultron_test_2b3_")

        # Initialize AgentMemoryBus & AgentManager
        self.bus = AgentMemoryBus()
        self.bus.initialize()
        self.manager = AgentManager(bus=self.bus)
        self.manager.initialize()

        # Instantiate agents
        self.bg_agent = BackgroundTaskAgent(bus=self.bus, worker_count=2)
        self.plan_agent = PlanningAgent(bus=self.bus)

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
    # BACKGROUND TASK AGENT TESTS (14 Scenarios)
    # =========================================================================

    def test_01_background_agent_registration(self) -> None:
        """Scenario 1: Registration of BackgroundTaskAgent with AgentManager and AgentRegistry."""
        success = self.manager.register_agent(self.bg_agent)
        self.assertTrue(success)
        self.assertIn("background_task_agent", [a["agent_id"] for a in self.manager.list_agents()])
        reg_agent = self.bus.agent_registry.get_agent("background_task_agent")
        self.assertIsNotNone(reg_agent)
        self.assertEqual(reg_agent.name, "Background Task Agent")

    def test_02_background_agent_capability_discovery(self) -> None:
        """Scenario 2: Capability discovery for BackgroundTaskAgent."""
        caps = self.bg_agent.capabilities
        self.assertIn("create_task", caps)
        self.assertIn("start_task", caps)
        self.assertIn("cancel_task", caps)
        self.assertIn("query_task_status", caps)
        self.assertIn("list_active_tasks", caps)
        self.assertIn("update_progress", caps)

    def test_03_background_agent_lifecycle(self) -> None:
        """Scenario 3: Lifecycle transitions of BackgroundTaskAgent (OFFLINE -> INITIALIZING -> ONLINE -> OFFLINE)."""
        self.assertEqual(self.bg_agent.status, AgentStatus.OFFLINE)
        self.bg_agent.initialize()
        self.assertEqual(self.bg_agent.status, AgentStatus.ONLINE)
        self.assertTrue(self.bg_agent.task_engine._is_running)
        self.bg_agent.shutdown()
        self.assertEqual(self.bg_agent.status, AgentStatus.OFFLINE)
        self.assertFalse(self.bg_agent.task_engine._is_running)

    def test_04_task_creation(self) -> None:
        """Scenario 4: Background task descriptor creation and WorkspaceStore persistence."""
        self.bg_agent.initialize()
        res = self.bg_agent.create_task({"action": "data_indexing", "description": "Index user files"})
        self.assertIn("task_id", res)
        t_id = res["task_id"]
        self.assertEqual(res["status"], TaskStatus.CREATED.value)

        # Check WorkspaceStore persistence
        ws_key = f"workspace/{self.bg_agent.agent_id}/tasks/{t_id}"
        ws_data = self.bus.read_workspace(ws_key, agent_id=self.bg_agent.agent_id)
        self.assertIsNotNone(ws_data)
        self.assertEqual(ws_data["action"], "data_indexing")
        self.bg_agent.shutdown()

    def test_05_task_execution(self) -> None:
        """Scenario 5: Enqueuing and executing a task via TaskEngine worker pool."""
        self.bg_agent.initialize()
        created = self.bg_agent.create_task({"action": "compute_hashes", "description": "Compute file hashes"})
        t_id = created["task_id"]

        exec_done = threading.Event()

        def custom_action():
            exec_done.set()

        start_res = self.bg_agent.start_task(t_id, exec_func=custom_action)
        self.assertIn(start_res["status"], [TaskStatus.RUNNING.value, TaskStatus.COMPLETED.value])

        # Wait for worker thread execution
        self.assertTrue(exec_done.wait(timeout=5.0))
        self.bg_agent.shutdown()

    def test_06_status_tracking(self) -> None:
        """Scenario 6: Querying task status throughout lifecycle."""
        self.bg_agent.initialize()
        created = self.bg_agent.create_task({"action": "log_compaction"})
        t_id = created["task_id"]

        status1 = self.bg_agent.get_task_status(t_id)
        self.assertEqual(status1["status"], TaskStatus.CREATED.value)

        self.bg_agent.start_task(t_id)
        time.sleep(0.1)

        status2 = self.bg_agent.get_task_status(t_id)
        self.assertIn(status2["status"], [TaskStatus.RUNNING.value, TaskStatus.COMPLETED.value])
        self.bg_agent.shutdown()

    def test_07_progress_tracking(self) -> None:
        """Scenario 7: Updating and querying task progress percentage."""
        self.bg_agent.initialize()
        created = self.bg_agent.create_task({"action": "file_sync"})
        t_id = created["task_id"]

        prog_res = self.bg_agent.update_progress(t_id, 45.5, message="Syncing chunk 2")
        self.assertEqual(prog_res["progress"], 45.5)

        status = self.bg_agent.get_task_status(t_id)
        self.assertEqual(status["progress"], 45.5)
        self.bg_agent.shutdown()

    def test_08_cancellation(self) -> None:
        """Scenario 8: Cancelling a running or pending task."""
        self.bg_agent.initialize()
        created = self.bg_agent.create_task({"action": "long_download"})
        t_id = created["task_id"]

        cancelled = self.bg_agent.cancel_task(t_id)
        self.assertTrue(cancelled)

        status = self.bg_agent.get_task_status(t_id)
        self.assertEqual(status["status"], TaskStatus.CANCELLED.value)
        self.bg_agent.shutdown()

    def test_09_failure_handling(self) -> None:
        """Scenario 9: Handling task execution exception and marking status FAILED/DLQ."""
        self.bg_agent.initialize()
        created = self.bg_agent.create_task({"action": "broken_job", "max_retries": 1})
        t_id = created["task_id"]

        def failing_action():
            raise RuntimeError("Simulated job crash.")

        self.bg_agent.start_task(t_id, exec_func=failing_action)
        time.sleep(0.3)  # Allow worker processing

        status = self.bg_agent.get_task_status(t_id)
        self.assertIn(status["status"], [TaskStatus.FAILED.value, TaskStatus.DLQ.value, TaskStatus.QUEUED.value])
        self.bg_agent.shutdown()

    def test_10_retry_recovery(self) -> None:
        """Scenario 10: Retrying a failed background task."""
        self.bg_agent.initialize()
        created = self.bg_agent.create_task({"action": "retryable_job", "max_retries": 3})
        t_id = created["task_id"]

        retry_res = self.bg_agent.retry_task(t_id)
        self.assertEqual(retry_res["task_id"], t_id)
        self.assertIn(retry_res["status"], [TaskStatus.RUNNING.value, TaskStatus.COMPLETED.value])

        status = self.bg_agent.get_task_status(t_id)
        self.assertGreaterEqual(status["retry_count"], 1)
        self.bg_agent.shutdown()

    def test_11_artifact_handling(self) -> None:
        """Scenario 11: Generating and registering an artifact for a background task."""
        self.bg_agent.initialize()
        created = self.bg_agent.create_task({"action": "report_generation"})
        t_id = created["task_id"]

        # Create dummy file artifact
        art_path = os.path.join(self.test_dir, "report.pdf")
        with open(art_path, "w", encoding="utf-8") as f:
            f.write("PDF Content")

        art_res = self.bg_agent.handle_artifact(t_id, art_path, mime_type="application/pdf")
        self.assertEqual(art_res["status"], "SUCCESS")
        self.assertIn("artifact", art_res)

        status = self.bg_agent.get_task_status(t_id)
        self.assertEqual(len(status["artifacts"]), 1)
        self.assertEqual(status["artifacts"][0]["file_path"], art_path)
        self.bg_agent.shutdown()

    def test_12_shutdown(self) -> None:
        """Scenario 12: Graceful shutdown of background task agent and task engine workers."""
        self.bg_agent.initialize()
        self.assertTrue(self.bg_agent.task_engine._is_running)
        self.bg_agent.shutdown()
        self.assertFalse(self.bg_agent.task_engine._is_running)
        self.assertEqual(self.bg_agent.status, AgentStatus.OFFLINE)

    def test_13_health_monitoring(self) -> None:
        """Scenario 13: Operational health_check() metric reporting."""
        self.bg_agent.initialize()
        self.bg_agent.create_task({"action": "task_1"})
        health = self.bg_agent.health_check()
        self.assertTrue(health["healthy"])
        self.assertEqual(health["managed_tasks_count"], 1)
        self.assertIn("engine_active_tasks", health)
        self.bg_agent.shutdown()

    def test_14_telemetry(self) -> None:
        """Scenario 14: Execution metrics telemetry logging."""
        self.bg_agent.initialize()
        self.bg_agent.execute_task("t_tel", {"action": "list_tasks"})
        health = self.bg_agent.health_check()
        self.assertEqual(health["metrics"]["tasks_executed"], 1)
        self.assertGreater(health["metrics"]["total_execution_time_ms"], 0.0)
        self.bg_agent.shutdown()

    # =========================================================================
    # PLANNING / REASONING AGENT TESTS (12 Scenarios)
    # =========================================================================

    def test_15_planning_agent_registration(self) -> None:
        """Scenario 15: Registration of PlanningAgent with AgentManager and AgentRegistry."""
        success = self.manager.register_agent(self.plan_agent)
        self.assertTrue(success)
        self.assertIn("planning_agent", [a["agent_id"] for a in self.manager.list_agents()])
        reg_agent = self.bus.agent_registry.get_agent("planning_agent")
        self.assertIsNotNone(reg_agent)

    def test_16_planning_agent_capability_discovery(self) -> None:
        """Scenario 16: Capability discovery for PlanningAgent."""
        caps = self.plan_agent.capabilities
        self.assertIn("create_plan", caps)
        self.assertIn("validate_plan_dependencies", caps)
        self.assertIn("track_plan_execution_state", caps)
        self.assertIn("produce_final_summary", caps)

    def test_17_planning_agent_lifecycle(self) -> None:
        """Scenario 17: Lifecycle transitions of PlanningAgent."""
        self.assertEqual(self.plan_agent.status, AgentStatus.OFFLINE)
        self.plan_agent.initialize()
        self.assertEqual(self.plan_agent.status, AgentStatus.ONLINE)
        self.plan_agent.shutdown()
        self.assertEqual(self.plan_agent.status, AgentStatus.OFFLINE)

    def test_18_plan_creation(self) -> None:
        """Scenario 18: Converting request into structured ExecutionPlan with PlanSteps."""
        self.plan_agent.initialize()
        steps_spec = [
            {"step_id": "s1", "description": "Scan apps", "required_capability": "app_discovery"},
            {"step_id": "s2", "description": "Launch app", "required_capability": "application_control", "dependencies": ["s1"]},
        ]
        plan = self.plan_agent.create_plan("Launch Chrome", steps_spec=steps_spec)
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].step_id, "s1")
        self.assertEqual(plan.steps[1].dependencies, ["s1"])

        # Check WorkspaceStore persistence
        ws_key = f"workspace/{self.plan_agent.agent_id}/plans/{plan.plan_id}"
        ws_data = self.bus.read_workspace(ws_key, agent_id=self.plan_agent.agent_id)
        self.assertIsNotNone(ws_data)
        self.assertEqual(ws_data["title"], "Plan: Launch Chrome")
        self.plan_agent.shutdown()

    def test_19_step_dependency_handling(self) -> None:
        """Scenario 19: Validating dependency ordering and relationship tree."""
        self.plan_agent.initialize()
        steps_spec = [
            {"step_id": "step_a", "description": "Fetch data", "required_capability": "retrieve_memory"},
            {"step_id": "step_b", "description": "Process data", "required_capability": "create_task", "dependencies": ["step_a"]},
        ]
        plan = self.plan_agent.create_plan("Data processing pipeline", steps_spec=steps_spec)
        validation = self.plan_agent.validate_plan(plan.plan_id)
        self.assertTrue(validation["valid"])
        self.assertEqual(len(validation["errors"]), 0)
        self.plan_agent.shutdown()

    def test_20_target_agent_selection(self) -> None:
        """Scenario 20: Selection of target domain agent for step capability."""
        self.plan_agent.initialize()
        target = self.plan_agent.select_target_agent("application_control")
        self.assertEqual(target, "system_agent")

        target_mem = self.plan_agent.select_target_agent("store_memory")
        self.assertEqual(target_mem, "memory_agent")
        self.plan_agent.shutdown()

    def test_21_plan_validation(self) -> None:
        """Scenario 21: Plan validation detecting invalid dependencies, cyclic dependencies, and missing capabilities."""
        self.plan_agent.initialize()
        # Invalid dependency step_z
        steps_spec = [
            {"step_id": "s1", "description": "Step 1", "required_capability": "unknown_cap", "dependencies": ["step_z"]},
        ]
        plan = self.plan_agent.create_plan("Faulty plan", steps_spec=steps_spec)
        val = self.plan_agent.validate_plan(plan.plan_id)
        self.assertFalse(val["valid"])
        self.assertGreater(len(val["errors"]), 0)
        self.plan_agent.shutdown()

    def test_22_failed_step_handling(self) -> None:
        """Scenario 22: Handling failed step execution and updating retry counters."""
        self.plan_agent.initialize()
        plan = self.plan_agent.create_plan("Test Plan")
        step_id = plan.steps[0].step_id

        res = self.plan_agent.handle_failed_step(plan.plan_id, step_id, "Connection timeout.")
        self.assertEqual(res["retry_count"], 1)
        self.assertTrue(res["can_retry"])
        self.assertEqual(res["step_status"], StepStatus.PENDING.value)
        self.plan_agent.shutdown()

    def test_23_retry_recovery(self) -> None:
        """Scenario 23: Retrying failed plan steps and updating plan status."""
        self.plan_agent.initialize()
        plan = self.plan_agent.create_plan("Test Plan")
        step_id = plan.steps[0].step_id

        self.plan_agent.handle_failed_step(plan.plan_id, step_id, "Error")
        success = self.plan_agent.retry_failed_step(plan.plan_id, step_id)
        self.assertTrue(success)

        val = self.plan_agent.update_step_status(plan.plan_id, step_id, StepStatus.COMPLETED)
        self.assertEqual(val["step_status"], StepStatus.COMPLETED.value)
        self.plan_agent.shutdown()

    def test_24_cancellation(self) -> None:
        """Scenario 24: Cancelling execution plan and marking steps CANCELLED."""
        self.plan_agent.initialize()
        plan = self.plan_agent.create_plan("Cancel test")
        cancelled = self.plan_agent.cancel_plan(plan.plan_id)
        self.assertTrue(cancelled)

        updated_plan = self.plan_agent._plans[plan.plan_id]
        self.assertEqual(updated_plan.status, PlanStatus.CANCELLED)
        self.assertEqual(updated_plan.steps[0].status, StepStatus.CANCELLED)
        self.assertTrue(updated_plan.steps[0].cancellation_state)
        self.plan_agent.shutdown()

    def test_25_execution_state_tracking(self) -> None:
        """Scenario 25: Tracking step progression through plan completion."""
        self.plan_agent.initialize()
        plan = self.plan_agent.create_plan("State tracking test")
        s1 = plan.steps[0].step_id
        s2 = plan.steps[1].step_id

        self.plan_agent.update_step_status(plan.plan_id, s1, StepStatus.COMPLETED)
        res2 = self.plan_agent.update_step_status(plan.plan_id, s2, StepStatus.COMPLETED)
        self.assertEqual(res2["plan_status"], PlanStatus.COMPLETED.value)
        self.plan_agent.shutdown()

    def test_26_final_summary_generation(self) -> None:
        """Scenario 26: Producing human-readable plan execution summary."""
        self.plan_agent.initialize()
        plan = self.plan_agent.create_plan("Summary test")
        s1 = plan.steps[0].step_id
        self.plan_agent.update_step_status(plan.plan_id, s1, StepStatus.COMPLETED)

        summary = self.plan_agent.generate_summary(plan.plan_id)
        self.assertIn("# Execution Summary:", summary)
        self.assertIn(plan.plan_id, summary)
        self.assertIn("Total Steps", summary)
        self.plan_agent.shutdown()

    # =========================================================================
    # INTEGRATION TESTS (6 Scenarios)
    # =========================================================================

    def test_27_agent_manager_integration(self) -> None:
        """Scenario 27: AgentManager managing combined lifecycles of BackgroundTaskAgent and PlanningAgent."""
        self.manager.register_agent(self.bg_agent)
        self.manager.register_agent(self.plan_agent)

        self.assertIn("background_task_agent", [a["agent_id"] for a in self.manager.list_agents()])
        self.assertIn("planning_agent", [a["agent_id"] for a in self.manager.list_agents()])

        self.assertEqual(self.bg_agent.status, AgentStatus.ONLINE)
        self.assertEqual(self.plan_agent.status, AgentStatus.ONLINE)
        self.manager.shutdown()

    def test_28_agent_registry_integration(self) -> None:
        """Scenario 28: Capability discovery across registered agents via AgentRegistry."""
        self.manager.register_agent(self.bg_agent)
        self.manager.register_agent(self.plan_agent)

        bg_agents = self.bus.find_agents_by_capability("create_task")
        self.assertEqual(len(bg_agents), 1)
        self.assertEqual(bg_agents[0].agent_id, "background_task_agent")

        plan_agents = self.bus.find_agents_by_capability("create_plan")
        self.assertEqual(len(plan_agents), 1)
        self.assertEqual(plan_agents[0].agent_id, "planning_agent")

    def test_29_agent_bus_communication(self) -> None:
        """Scenario 29: Inter-agent messaging between BackgroundTaskAgent and PlanningAgent over AgentMemoryBus."""
        self.manager.register_agent(self.bg_agent)
        self.manager.register_agent(self.plan_agent)

        msg_id = self.plan_agent.send_message(
            recipient_id="background_task_agent",
            payload={"action": "create_task", "description": "Execute background step"},
            topic="task_request",
        )
        self.assertTrue(len(msg_id) > 0)

        recv_msg = self.bg_agent.receive_message(timeout=1.0)
        self.assertIsNotNone(recv_msg)
        self.assertEqual(recv_msg.sender_id, "planning_agent")
        self.assertEqual(recv_msg.payload["action"], "create_task")
        self.bg_agent.acknowledge_message(recv_msg.message_id)

    def test_30_workspace_acl_enforcement(self) -> None:
        """Scenario 30: WorkspaceStore persistence with WorkspaceACL tier validation."""
        self.manager.register_agent(self.bg_agent)
        self.manager.register_agent(self.plan_agent)

        # BackgroundTaskAgent writes task
        ws_key = f"workspace/{self.bg_agent.agent_id}/tasks/tsk_acl_1"
        self.bg_agent.write_workspace(ws_key, {"status": "CREATED"}, task_id="tsk_acl_1")

        # Verify reading works for owner
        read_val = self.bg_agent.read_workspace(ws_key, task_id="tsk_acl_1")
        self.assertEqual(read_val["status"], "CREATED")

        # Explicitly grant owner tier to background_task_agent and test DENIED for un-permitted agent
        self.bus.grant_permission(ws_key, "background_task_agent", AccessTier.OWNER)
        with self.assertRaises(PermissionDeniedException):
            self.bus.write_workspace(ws_key, {"status": "MUTATED"}, owner_agent="unauthorized_agent")

    def test_31_orchestrator_dispatch_integration(self) -> None:
        """Scenario 31: Orchestrator dispatching tasks to BackgroundTaskAgent and PlanningAgent via AgentManager."""
        self.manager.register_agent(self.bg_agent)
        self.manager.register_agent(self.plan_agent)

        # Dispatch task to PlanningAgent
        plan_res = self.manager.dispatch_task(
            "planning_agent",
            "task_orch_plan",
            {"command": "create_plan", "request": "Organize workspace files"},
        )
        self.assertEqual(plan_res["status"], "SUCCESS")
        self.assertIn("plan_id", plan_res["result"])

        # Dispatch task to BackgroundTaskAgent
        bg_res = self.manager.dispatch_task(
            "background_task_agent",
            "task_orch_bg",
            {"command": "create_task", "action": "clean_temp_files"},
        )
        self.assertEqual(bg_res["status"], "SUCCESS")
        self.assertIn("task_id", bg_res["result"])

    def test_32_graceful_system_shutdown(self) -> None:
        """Scenario 32: Graceful system shutdown of all agents, services, worker threads, and memory bus."""
        self.manager.register_agent(self.bg_agent)
        self.manager.register_agent(self.plan_agent)

        self.assertEqual(self.bg_agent.status, AgentStatus.ONLINE)
        self.assertEqual(self.plan_agent.status, AgentStatus.ONLINE)

        self.manager.shutdown()
        self.bus.shutdown()

        self.assertEqual(self.bg_agent.status, AgentStatus.OFFLINE)
        self.assertEqual(self.plan_agent.status, AgentStatus.OFFLINE)
        self.assertFalse(self.bg_agent.task_engine._is_running)


if __name__ == "__main__":
    unittest.main()
