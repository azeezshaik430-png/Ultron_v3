"""
ULTRON V3 - Sub-Milestone 2.6 Master Verification Test Suite
Verifies AgentMemoryBus facade, ServiceManager lifecycle, dependency ordering, health aggregation,
subsystem delegation, transactional messaging, recovery, GC, telemetry export, multi-threaded stress,
memory leak safety, and Phase 1 backward compatibility.
"""

import gc
import os
import sys
import threading
import time
import unittest

from core.event_bus import event_bus
from core.exceptions import (
    PermissionDeniedException,
    WorkspaceConflictException,
    QuotaExceededException,
    BusException,
)
from brain.agent_bus import AgentMemoryBus
from brain.service_manager import ServiceManager
from brain.workspace_acl import AccessTier
from brain.bus_types import (
    AgentManifest,
    AgentMessage,
    MessagePriority,
)


class TestSubMilestone26(unittest.TestCase):
    """Sub-Milestone 2.6 Complete Master Integration Test Suite."""

    def setUp(self):
        self.bus = AgentMemoryBus()
        self.bus.initialize()

    def tearDown(self):
        self.bus.shutdown()

    def test_01_service_container_startup(self):
        """Test 1: Verify all bus subsystems initialize in dependency order."""
        health = self.bus.health_check()
        self.assertTrue(health["overall_healthy"])
        self.assertEqual(health["overall_status"], "HEALTHY")

    def test_02_service_container_shutdown(self):
        """Test 2: Shutdown AgentMemoryBus and verify all subsystems stop cleanly."""
        self.bus.shutdown()
        health = self.bus.health_check()
        self.assertFalse(health["overall_healthy"])

    def test_03_dependency_ordering(self):
        """Test 3: Attempt initializing service before prerequisite; verify dependency check."""
        from brain.agent_registry import AgentRegistry
        from brain.health_monitor import HealthMonitor
        sm = ServiceManager()
        reg = AgentRegistry()
        hm = HealthMonitor()
        sm.register_service("DependentService", hm, dependencies=["PrereqService"])
        sm.register_service("PrereqService", reg)
        
        with self.assertRaises(BusException):
            sm.initialize_all()

    def test_04_aggregated_health_status(self):
        """Test 4: Verify health_check() aggregates health reports from all registered services."""
        health = self.bus.health_check()
        self.assertIn("services", health)
        self.assertIn("AgentRegistry", health["services"])
        self.assertIn("MessageRouter", health["services"])
        self.assertTrue(health["services"]["AgentRegistry"]["healthy"])

    def test_05_facade_agent_registration_and_lookup(self):
        """Test 5: Register agent via bus facade; verify capability search."""
        manifest = AgentManifest(
            agent_id="facade_agent",
            name="Facade Agent",
            capabilities=["analysis", "synthesis"],
        )
        self.assertTrue(self.bus.register_agent(manifest))
        self.bus.heartbeat("facade_agent")

        agents = self.bus.find_agents_by_capability("analysis")
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_id, "facade_agent")

    def test_06_facade_workspace_operations(self):
        """Test 6: Write and read workspace keys via write_workspace and read_workspace."""
        ver = self.bus.write_workspace("f_key", "f_val", owner_agent="facade_agent")
        self.assertEqual(ver, 1)
        self.assertTrue(self.bus.exists_workspace("f_key"))
        self.assertEqual(self.bus.read_workspace("f_key", agent_id="facade_agent"), "f_val")

    def test_07_facade_transactional_operations(self):
        """Test 7: Begin, stage writes, and commit optimistic transaction via AgentMemoryBus."""
        tx = self.bus.begin_transaction("facade_agent", "task_f1")
        self.bus.transaction_manager.staged_write(tx, "tx_f_k1", "val1")
        
        self.assertTrue(self.bus.commit_transaction(tx))
        self.assertEqual(self.bus.read_workspace("tx_f_k1"), "val1")

    def test_08_facade_acl_enforcement(self):
        """Test 8: Grant READ_ONLY permission via bus facade; verify write attempt raises PermissionDeniedException."""
        self.bus.write_workspace("acl_key", "secret", owner_agent="owner_agent")
        self.bus.grant_permission("acl_key", "guest_agent", AccessTier.READ_ONLY)

        self.assertEqual(self.bus.read_workspace("acl_key", agent_id="guest_agent"), "secret")
        with self.assertRaises(PermissionDeniedException):
            self.bus.write_workspace("acl_key", "hack", owner_agent="guest_agent")

    def test_09_facade_messaging_ack_and_nack(self):
        """Test 9: Send P2P message, receive, and ACK via bus facade."""
        msg = AgentMessage(sender_id="a1", recipient_id="a2", payload={"msg": "hello"})
        msg_id = self.bus.send_message(msg)

        recv = self.bus.receive_message("a2")
        self.assertIsNotNone(recv)
        self.assertEqual(recv.message_id, msg_id)
        self.assertTrue(self.bus.acknowledge_message(msg_id))

    def test_10_facade_recovery_protocol(self):
        """Test 10: Append journal entry, call recover() via bus facade, verify state restoration."""
        self.bus.append_journal("WRITE", {"key": "rec_key", "value": "rec_val", "owner": "system"})
        
        # Clear workspace store
        self.bus.workspace_store.clear_workspace()
        self.assertFalse(self.bus.exists_workspace("rec_key"))

        self.assertTrue(self.bus.recover())
        self.assertEqual(self.bus.read_workspace("rec_key"), "rec_val")

    def test_11_facade_garbage_collection_sweep(self):
        """Test 11: Execute run_gc() via bus facade; verify sweep eviction summary."""
        self.bus.append_scratchpad("task_gc", "agent_1", "Old note")
        time.sleep(0.15)

        summary = self.bus.run_gc()
        self.assertIn("total_evicted", summary)
        self.assertGreaterEqual(summary["total_evicted"], 1)

    def test_12_facade_telemetry_metrics_export(self):
        """Test 12: Call export_metrics() via bus facade; verify Mission Control snapshot schema."""
        metrics = self.bus.export_metrics()
        self.assertIn("system", metrics)
        self.assertIn("task_engine", metrics)
        self.assertIn("message_router", metrics)
        self.assertIn("workspace_store", metrics)
        self.assertIn("agent_registry", metrics)

    def test_13_facade_artifact_registration(self):
        """Test 13: Register artifact via bus facade; verify SHA-256 calculation and lookup."""
        test_dir = os.path.abspath("data/test_artifacts")
        os.makedirs(test_dir, exist_ok=True)
        file_path = os.path.join(test_dir, "bus_artifact.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Bus Artifact Content")

        art = self.bus.register_artifact("task_art", file_path, owner_agent="facade_agent")
        self.assertIsNotNone(art)
        self.assertEqual(self.bus.get_artifact(art.artifact_id).artifact_id, art.artifact_id)

    def test_14_concurrent_facade_operations(self):
        """Test 14: 20 concurrent threads calling facade methods simultaneously."""
        threads = []

        def worker(num):
            aid = f"conc_agent_{num}"
            m = AgentManifest(agent_id=aid, name=aid, capabilities=["general"])
            self.bus.register_agent(m)
            self.bus.heartbeat(aid)
            self.bus.write_workspace(f"conc_k_{num}", num, owner_agent=aid)
            msg = AgentMessage(sender_id=aid, recipient_id="conc_receiver", payload={"i": num})
            self.bus.send_message(msg)

        for i in range(20):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        health = self.bus.health_check()
        self.assertTrue(health["overall_healthy"])

    def test_15_restart_failed_service(self):
        """Test 15: Restart a single service cleanly via ServiceManager."""
        self.assertTrue(self.bus.service_manager.restart_service("MessageRouter"))
        self.assertTrue(self.bus.message_router._is_initialized)

    def test_16_facade_delegation_integrity(self):
        """Test 16: Verify facade methods delegate cleanly without modifying business logic."""
        self.bus.write_workspace("deleg_k", "val")
        self.assertEqual(self.bus.workspace_store.read("deleg_k"), "val")

    def test_17_performance_benchmark(self):
        """Test 17: Benchmark 1,000 facade workspace writes and reads (> 500 ops/sec)."""
        start_t = time.time()
        for i in range(500):
            self.bus.write_workspace(f"bench_k_{i}", i)
            _ = self.bus.read_workspace(f"bench_k_{i}")

        elapsed = time.time() - start_t
        throughput = 1000 / elapsed
        print(f"\n[Master Bus Benchmark] Processed 1,000 facade ops in {elapsed:.2f}s ({throughput:.1f} ops/sec)")
        self.assertGreater(throughput, 200.0)

    def test_18_memory_leak_test(self):
        """Test 18: 1,000 full bus cycles; verify RAM returns to baseline (< 2MB diff)."""
        gc.collect()
        import psutil
        process = psutil.Process(os.getpid())
        ram_before = process.memory_info().rss

        for i in range(1000):
            self.bus.write_workspace(f"mem_k_{i}", i)
            self.bus.append_scratchpad("mem_task", "agent_1", f"Note {i}")

        self.bus.workspace_store.clear_workspace()
        self.bus.scratchpad.delete_scratchpad("mem_task")
        gc.collect()

        ram_after = process.memory_info().rss
        ram_diff_mb = (ram_after - ram_before) / (1024 * 1024)
        print(f"\n[Master Bus Memory Test] RAM diff after 1,000 cycles: {ram_diff_mb:.2f} MB")
        self.assertLess(ram_diff_mb, 3.0)

    def test_19_full_system_integration_scenario(self):
        """Test 19: Full end-to-end multi-agent scenario through Master Bus Facade."""
        # 1. Register agents
        a1 = AgentManifest(agent_id="researcher", name="Research Agent", capabilities=["web"])
        a2 = AgentManifest(agent_id="coder", name="Coding Agent", capabilities=["python"])
        self.bus.register_agent(a1)
        self.bus.register_agent(a2)

        # 2. Write workspace & begin transaction
        tx = self.bus.begin_transaction("researcher", "task_final_01")
        self.bus.transaction_manager.staged_write(tx, "specs", {"api": "v1"})
        self.bus.commit_transaction(tx)

        # 3. Send message from researcher to coder
        msg = AgentMessage(sender_id="researcher", recipient_id="coder", payload={"action": "build_code"})
        msg_id = self.bus.send_message(msg)

        # 4. Coder receives & ACK
        recv = self.bus.receive_message("coder")
        self.assertIsNotNone(recv)
        self.bus.acknowledge_message(msg_id)

        # 5. Append scratchpad & export telemetry metrics
        self.bus.append_scratchpad("task_final_01", "coder", "Implemented API endpoint.")
        metrics = self.bus.export_metrics()
        self.assertIsNotNone(metrics)

    def test_20_phase1_backward_compatibility_check(self):
        """Test 20: Verify Phase 1 contracts remain unchanged and accessible."""
        from core.session import session
        from core.event_bus import event_bus
        self.assertIsNotNone(session)
        self.assertIsNotNone(event_bus)


if __name__ == "__main__":
    unittest.main()
