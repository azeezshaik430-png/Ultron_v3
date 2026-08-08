"""
ULTRON V3 - Sub-Milestone 2B.1 Unit Test Suite
Core Agent Base Architecture + Agent Manager Verification.
"""

import time
import unittest
from typing import Dict, Any

from agents.base_ultron_agent import BaseUltronAgent
from brain.agent_manager import AgentManager, agent_manager
from brain.agent_bus import AgentMemoryBus
from brain.bus_types import (
    AgentStatus,
    CircuitBreakerState,
    MessagePriority,
)
from core.exceptions import PermissionDeniedException
from brain.workspace_acl import AccessTier


class MockTestAgent(BaseUltronAgent):
    """Concrete mock agent implementation for 2B.1 testing."""

    def __init__(self, agent_id: str = "agent.mock", bus: Any = None) -> None:
        super().__init__(
            agent_id=agent_id,
            name="MockTestAgent",
            description="Mock agent for 2B.1 architecture unit tests",
            capabilities=["TEST_CAPABILITY", "MOCK_PROCESSING"],
            supported_skills=["mock_skill"],
            bus=bus,
        )
        self.last_payload = None

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        self.last_payload = payload
        if payload.get("should_fail"):
            raise ValueError("Simulated task execution failure")
        return f"Mock output for {payload.get('task', 'unknown')}"


class TestSubMilestone2B1(unittest.TestCase):
    """Sub-Milestone 2B.1 Unit Verification Test Suite."""

    def setUp(self) -> None:
        self.bus = AgentMemoryBus()
        self.bus.initialize()
        self.manager = AgentManager(bus=self.bus)
        self.agent = MockTestAgent(agent_id="agent.mock", bus=self.bus)

    def tearDown(self) -> None:
        if self.manager._is_initialized:
            self.manager.shutdown()
        else:
            self.bus.shutdown()

    def test_01_agent_registration_and_duplicate_rejection(self):
        """Test 1: Verify agent registration and rejection of duplicate IDs/names."""
        # Test valid registration
        res1 = self.manager.register_agent(self.agent)
        self.assertTrue(res1)
        self.assertEqual(len(self.manager._agents), 1)

        # Test duplicate agent_id registration rejection
        dup_agent_id = MockTestAgent(agent_id="agent.mock", bus=self.bus)
        res2 = self.manager.register_agent(dup_agent_id)
        self.assertFalse(res2)

        # Test duplicate name registration rejection
        dup_name = MockTestAgent(agent_id="agent.mock2", bus=self.bus)
        dup_name.name = "MockTestAgent"
        res3 = self.manager.register_agent(dup_name)
        self.assertFalse(res3)

    def test_02_capability_discovery(self):
        """Test 2: Verify capability discovery and lookup by agent_id or name."""
        self.manager.register_agent(self.agent)
        self.manager.initialize()

        # Capability lookup
        found = self.manager.find_agents_by_capability("TEST_CAPABILITY")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].agent_id, "agent.mock")

        # Non-existent capability
        not_found = self.manager.find_agents_by_capability("NON_EXISTENT")
        self.assertEqual(len(not_found), 0)

        # Lookup by agent_id or name
        by_id = self.manager.get_agent("agent.mock")
        by_name = self.manager.get_agent("MockTestAgent")
        self.assertIsNotNone(by_id)
        self.assertIsNotNone(by_name)
        self.assertEqual(by_id, by_name)

    def test_03_lifecycle_startup_and_shutdown(self):
        """Test 3: Verify agent initialization, heartbeat thread, and shutdown."""
        self.manager.register_agent(self.agent)
        self.assertEqual(self.agent.status, AgentStatus.OFFLINE)

        # Initialize manager and agent
        self.manager.initialize()
        self.assertEqual(self.agent.status, AgentStatus.ONLINE)
        self.assertTrue(self.agent._is_initialized)
        self.assertIsNotNone(self.agent._heartbeat_thread)

        # Shutdown manager and agent
        self.manager.shutdown()
        self.assertEqual(self.agent.status, AgentStatus.OFFLINE)
        self.assertFalse(self.agent._is_initialized)

    def test_04_health_integration_and_heartbeats(self):
        """Test 4: Verify health inspection telemetry and heartbeat monitor integration."""
        self.manager.register_agent(self.agent)
        self.manager.initialize()

        # Send manual heartbeat
        self.bus.heartbeat("agent.mock")
        health = self.manager.health_check()

        self.assertTrue(health["healthy"])
        self.assertIn("agent.mock", health["agent_health"])
        self.assertTrue(health["agent_health"]["agent.mock"]["healthy"])

    def test_05_permission_and_acl_enforcement(self):
        """Test 5: Verify agent workspace operations respect WorkspaceACL."""
        self.manager.register_agent(self.agent)
        self.manager.initialize()

        key = "workspace/agent.mock/test_key"
        val = {"data": 123}

        # Write to owned key space
        version = self.agent.write_workspace(key, val, task_id="task_1")
        self.assertGreater(version, 0)

        # Read back from workspace
        read_val = self.agent.read_workspace(key, task_id="task_1")
        self.assertEqual(read_val, val)

    def test_06_task_dispatch_and_execution(self):
        """Test 6: Verify task dispatch via AgentManager to registered agent."""
        self.manager.register_agent(self.agent)
        self.manager.initialize()

        payload = {"task": "Process test data", "data": [1, 2, 3]}
        res = self.manager.dispatch_task("agent.mock", "task_100", payload)

        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["task_id"], "task_100")
        self.assertIn("Mock output", res["result"])
        self.assertEqual(self.agent.last_payload, payload)

    def test_07_cancellation_and_error_handling(self):
        """Test 7: Verify task cancellation and exception error payload formatting."""
        self.manager.register_agent(self.agent)
        self.manager.initialize()

        # Error handling test
        fail_payload = {"task": "Failing task", "should_fail": True}
        res = self.manager.dispatch_task("agent.mock", "task_fail", fail_payload)

        self.assertEqual(res["status"], "ERROR")
        self.assertIn("Simulated task execution failure", res["error"])
        # Verify status restored to ONLINE after error
        self.assertEqual(self.agent.status, AgentStatus.ONLINE)

        # Cancellation test
        self.agent._active_tasks["task_cancel_target"] = {"started_at": time.time()}
        self.agent.status = AgentStatus.BUSY
        cancelled = self.manager.cancel_task("task_cancel_target", agent_id="agent.mock")
        self.assertTrue(cancelled)
        self.assertEqual(self.agent.status, AgentStatus.ONLINE)

    def test_08_message_bus_p2p_messaging(self):
        """Test 8: Verify agent-to-bus message sending, receiving, and ACK."""
        receiver = MockTestAgent(agent_id="agent.receiver", bus=self.bus)
        receiver.name = "ReceiverAgent"
        self.manager.register_agent(self.agent)
        self.manager.register_agent(receiver)
        self.manager.initialize()

        # Send P2P message envelope
        msg_id = self.agent.send_message("agent.receiver", {"greeting": "Hello receiver"}, priority=MessagePriority.HIGH)
        self.assertIsNotNone(msg_id)

        # Receiver fetches envelope from inbox
        env = receiver.receive_message(timeout=0.2)
        self.assertIsNotNone(env)
        self.assertEqual(env.sender_id, "agent.mock")
        self.assertEqual(env.payload["greeting"], "Hello receiver")

        # Receiver acknowledges message
        acked = receiver.acknowledge_message(env.message_id)
        self.assertTrue(acked)

    def test_09_telemetry_metrics_and_scratchpad(self):
        """Test 9: Verify scratchpad logging and telemetry metrics collection."""
        self.manager.register_agent(self.agent)
        self.manager.initialize()

        payload = {"task": "Telemetry test"}
        self.manager.dispatch_task("agent.mock", "task_telemetry", payload)

        # Verify scratchpad entries
        notes = self.bus.read_scratchpad("task_telemetry")
        self.assertGreater(len(notes), 0)

        # Verify agent metrics
        health = self.agent.health_check()
        metrics = health["metrics"]
        self.assertEqual(metrics["tasks_executed"], 1)
        self.assertGreater(metrics["total_execution_time_ms"], 0.0)

    def test_10_circuit_breaker_rejection(self):
        """Test 10: Verify AgentManager rejects dispatch when HealthMonitor circuit breaker is OPEN."""
        self.manager.register_agent(self.agent)
        self.manager.initialize()

        # Manually force circuit breaker OPEN in HealthMonitor
        self.bus.health_monitor._circuit_breakers["agent.mock"] = CircuitBreakerState.OPEN

        payload = {"task": "Blocked task"}
        res = self.manager.dispatch_task("agent.mock", "task_blocked", payload)

        self.assertEqual(res["status"], "ERROR")
        self.assertIn("Circuit breaker OPEN", res["error"])


if __name__ == "__main__":
    unittest.main()
