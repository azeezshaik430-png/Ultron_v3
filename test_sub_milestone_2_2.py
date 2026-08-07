"""
ULTRON V3 - Sub-Milestone 2.2 Verification Test Suite
Verifies AgentRegistry manifest registration, capability indexing, status tracking,
HealthMonitor heartbeat inspection, circuit breaker state machine, health snapshots,
duplicate agent re-registration, multi-threaded concurrency, and Phase 1 compatibility.
"""

import gc
import os
import random
import sys
import threading
import time
import unittest

from core.event_bus import event_bus
from brain.agent_registry import AgentRegistry
from brain.health_monitor import HealthMonitor
from brain.bus_types import (
    AgentManifest,
    AgentStatus,
    CircuitBreakerState,
)


class TestSubMilestone22(unittest.TestCase):
    """Sub-Milestone 2.2 Complete Test Suite."""

    def setUp(self):
        self.registry = AgentRegistry()
        self.registry.initialize()
        self.monitor = HealthMonitor(
            inspection_interval=0.2,
            heartbeat_timeout=0.5,
            failure_threshold=3,
        )
        self.monitor.initialize()

    def tearDown(self):
        self.monitor.shutdown()
        self.registry.shutdown()

    def test_01_agent_registration_and_capability_index(self):
        """Test 1: Register subagent manifests and test O(1) capability lookup."""
        manifest_a = AgentManifest(
            agent_id="research_agent",
            name="Research Agent",
            capabilities=["web_search", "scraping"],
        )
        manifest_b = AgentManifest(
            agent_id="coding_agent",
            name="Coding Agent",
            capabilities=["code_gen", "scraping"],
        )

        self.assertTrue(self.registry.register_agent(manifest_a))
        self.assertTrue(self.registry.register_agent(manifest_b))

        searchers = self.registry.find_agents_by_capability("web_search")
        self.assertEqual(len(searchers), 1)
        self.assertEqual(searchers[0].agent_id, "research_agent")

        scrapers = self.registry.find_agents_by_capability("scraping")
        self.assertEqual(len(scrapers), 2)

    def test_02_unregistration_and_index_cleanup(self):
        """Test 2: Unregister agent and verify capability index cleanup."""
        manifest = AgentManifest(
            agent_id="temp_agent",
            name="Temp Agent",
            capabilities=["temp_capability"],
        )

        self.registry.register_agent(manifest)
        self.assertEqual(len(self.registry.find_agents_by_capability("temp_capability")), 1)

        self.assertTrue(self.registry.unregister_agent("temp_agent"))
        self.assertEqual(len(self.registry.find_agents_by_capability("temp_capability")), 0)

    def test_03_status_transitions_and_metrics(self):
        """Test 3: Verify subagent status updates and registry metrics aggregation."""
        manifest = AgentManifest(agent_id="agent_1", name="Agent 1")
        self.registry.register_agent(manifest)

        self.registry.update_status("agent_1", AgentStatus.BUSY)
        metrics = self.registry.get_registry_metrics()
        self.assertEqual(metrics["total_agents"], 1)
        self.assertEqual(metrics["busy_agents"], 1)

    def test_04_heartbeat_and_missing_heartbeat_detection(self):
        """Test 4: Send heartbeat, simulate timeout, and verify HEALTH_UNHEALTHY event."""
        unhealthy_events = []
        event_bus.subscribe("AGENT_UNHEALTHY", lambda **p: unhealthy_events.append(p))

        self.monitor.register_monitored_agent("agent_hb_test")
        self.monitor.heartbeat("agent_hb_test")

        # Wait for timeout (heartbeat_timeout = 0.5s)
        time.sleep(0.8)

        snapshot = self.monitor.get_health_snapshot()
        self.assertIn("agent_hb_test", snapshot)
        self.assertFalse(snapshot["agent_hb_test"]["healthy"])
        self.assertGreaterEqual(len(unhealthy_events), 1)

    def test_05_circuit_breaker_state_machine(self):
        """Test 5: Record failures and verify circuit breaker transitions CLOSED -> OPEN -> reset."""
        cb_events = []
        event_bus.subscribe("CIRCUIT_BREAKER_TRIPPED", lambda **p: cb_events.append(p))

        self.monitor.register_monitored_agent("cb_agent")
        self.assertEqual(self.monitor.get_circuit_breaker_state("cb_agent"), CircuitBreakerState.CLOSED)

        self.monitor.record_failure("cb_agent", "Error 1")
        self.monitor.record_failure("cb_agent", "Error 2")
        self.assertEqual(self.monitor.get_circuit_breaker_state("cb_agent"), CircuitBreakerState.CLOSED)

        self.monitor.record_failure("cb_agent", "Error 3")
        self.assertEqual(self.monitor.get_circuit_breaker_state("cb_agent"), CircuitBreakerState.OPEN)
        self.assertGreaterEqual(len(cb_events), 1)

        self.monitor.reset_circuit_breaker("cb_agent")
        self.assertEqual(self.monitor.get_circuit_breaker_state("cb_agent"), CircuitBreakerState.CLOSED)

    def test_06_health_snapshot_api(self):
        """Test 6: Verify get_health_snapshot() API formatting."""
        self.monitor.register_monitored_agent("snap_agent")
        self.monitor.heartbeat("snap_agent")

        snap = self.monitor.get_health_snapshot()
        self.assertIn("snap_agent", snap)
        self.assertTrue(snap["snap_agent"]["healthy"])
        self.assertEqual(snap["snap_agent"]["circuit_breaker"], "CLOSED")

    def test_07_multi_threaded_concurrent_heartbeats(self):
        """Test 7: 20 concurrent threads recording heartbeats simultaneously."""
        self.monitor.register_monitored_agent("concurrent_agent")
        threads = []

        def worker():
            for _ in range(50):
                self.monitor.heartbeat("concurrent_agent")

        for _ in range(20):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        snap = self.monitor.get_health_snapshot()
        self.assertTrue(snap["concurrent_agent"]["healthy"])

    def test_08_duplicate_agent_registration_handling(self):
        """Test 8: Re-register agent with updated capabilities cleanly."""
        manifest1 = AgentManifest(agent_id="dup_agent", name="V1", capabilities=["cap_v1"])
        manifest2 = AgentManifest(agent_id="dup_agent", name="V2", capabilities=["cap_v2"])

        self.registry.register_agent(manifest1)
        self.assertEqual(len(self.registry.find_agents_by_capability("cap_v1")), 1)

        # Duplicate re-registration
        self.registry.register_agent(manifest2)
        self.assertEqual(len(self.registry.find_agents_by_capability("cap_v1")), 0)
        self.assertEqual(len(self.registry.find_agents_by_capability("cap_v2")), 1)
        self.assertEqual(self.registry.get_agent("dup_agent").name, "V2")

    def test_09_concurrent_register_unregister_stress(self):
        """Test 9: 20 concurrent threads randomly registering and unregistering agents."""
        threads = []

        def worker(num):
            for i in range(20):
                aid = f"stress_agent_{num}_{i}"
                m = AgentManifest(agent_id=aid, name=aid, capabilities=[f"cap_{num}"])
                self.registry.register_agent(m)
                time.sleep(0.001)
                self.registry.unregister_agent(aid)

        for i in range(20):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        metrics = self.registry.get_registry_metrics()
        self.assertEqual(metrics["total_agents"], 0)

    def test_10_phase1_backward_compatibility_check(self):
        """Test 10: Verify Phase 1 contracts remain unchanged and accessible."""
        from core.session import session
        from core.event_bus import event_bus
        self.assertIsNotNone(session)
        self.assertIsNotNone(event_bus)


if __name__ == "__main__":
    unittest.main()
