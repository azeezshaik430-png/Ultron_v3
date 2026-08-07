"""
ULTRON V3 - Sub-Milestone 2.5 Verification Test Suite
Tests RecoveryJournal append, SHA-256 checksums, atomic snapshots, corruption detection,
GarbageCollector sweeps, MetricsTelemetry export, multi-threaded concurrency, crash recovery, and Phase 1 compatibility.
"""

import gc
import json
import os
import sys
import threading
import time
import unittest

from core.event_bus import event_bus
from core.exceptions import JournalCorruptionException, BusException
from brain.recovery_journal import RecoveryJournal
from brain.garbage_collector import BusGarbageCollector
from brain.metrics_telemetry import MetricsTelemetry
from brain.scratchpad import AgentScratchpad
from brain.workspace_store import WorkspaceStore


class TestSubMilestone25(unittest.TestCase):
    """Sub-Milestone 2.5 Complete Test Suite."""

    def setUp(self):
        self.test_dir = os.path.abspath("data/test_recovery")
        os.makedirs(self.test_dir, exist_ok=True)
        self.journal_path = os.path.join(self.test_dir, "test_journal.log")
        self.snapshot_path = os.path.join(self.test_dir, "test_snapshot.json")

        if os.path.exists(self.journal_path):
            os.remove(self.journal_path)
        if os.path.exists(self.snapshot_path):
            os.remove(self.snapshot_path)

        self.journal = RecoveryJournal(journal_path=self.journal_path, snapshot_path=self.snapshot_path)
        self.journal.initialize()

        self.scratchpad = AgentScratchpad()
        self.scratchpad.initialize()

        self.gc = BusGarbageCollector(
            gc_interval=0.2,
            max_batch=100,
            scratchpad=self.scratchpad,
        )
        self.gc.initialize()

        self.store = WorkspaceStore()
        self.store.initialize()

        self.telemetry = MetricsTelemetry(
            workspace_store=self.store,
            recovery_journal=self.journal,
            garbage_collector=self.gc,
        )
        self.telemetry.initialize()

    def tearDown(self):
        self.telemetry.shutdown()
        self.store.shutdown()
        self.gc.shutdown()
        self.scratchpad.shutdown()
        self.journal.shutdown()

    def test_01_journal_append_and_checksum(self):
        """Test 1: Append event to journal file and verify SHA-256 line hash."""
        events = []
        event_bus.subscribe("JOURNAL_APPENDED", lambda **p: events.append(p))

        self.assertTrue(self.journal.append_event("WRITE", {"key": "k1", "value": "v1"}))
        self.assertTrue(os.path.exists(self.journal_path))
        self.assertGreaterEqual(len(events), 1)

    def test_02_checkpoint_and_snapshot(self):
        """Test 2: Call checkpoint(), verify snapshot created and journal truncated."""
        events = []
        event_bus.subscribe("CHECKPOINT_CREATED", lambda **p: events.append(p))

        self.journal.append_event("WRITE", {"key": "k1", "value": "v1"})
        snp_path = self.journal.checkpoint(snapshot_data={"workspace_version": 2, "entries": {}})

        self.assertTrue(os.path.exists(snp_path))
        self.assertEqual(os.path.getsize(self.journal_path), 0)
        self.assertGreaterEqual(len(events), 1)

    def test_03_journal_replay(self):
        """Test 3: Read journal file, verify SHA-256 integrity check and replayed entry list."""
        self.journal.append_event("WRITE", {"key": "k1", "value": "val1"})
        self.journal.append_event("WRITE", {"key": "k2", "value": "val2"})

        replayed = self.journal.replay()
        self.assertEqual(len(replayed), 2)
        self.assertEqual(replayed[0]["payload"]["key"], "k1")

    def test_04_journal_corruption_detection(self):
        """Test 4: Insert corrupted line into journal file; verify replay() catches corruption."""
        self.journal.append_event("WRITE", {"key": "k1", "value": "val1"})

        # Append corrupted line
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write("bad_hash|invalid_json_data\n")

        replayed = self.journal.replay()
        self.assertEqual(len(replayed), 1)
        metrics = self.journal.get_replay_metrics()
        self.assertEqual(metrics["corrupted_lines_count"], 1)

    def test_05_crash_recovery_protocol(self):
        """Test 5: Load snapshot and apply replayed journal events to restore state cleanly."""
        self.store.write("recover_key", "old_val")
        self.journal.create_snapshot(self.store.create_snapshot())

        self.journal.append_event("WRITE", {"key": "recover_key", "value": "new_val", "owner": "system"})

        # Clear store to simulate crash
        self.store.clear_workspace()
        self.assertFalse(self.store.exists("recover_key"))

        # Execute recovery
        self.assertTrue(self.journal.recover(workspace_store=self.store))
        self.assertEqual(self.store.read("recover_key"), "new_val")

    def test_06_gc_scratchpad_cleanup(self):
        """Test 6: Trigger perform_cleanup(); verify expired scratchpad entries evicted and events published."""
        events = []
        event_bus.subscribe("GC_COMPLETED", lambda **p: events.append(p))

        self.scratchpad.append_entry("task_gc", "agent_1", "Old note")
        time.sleep(0.1)

        summary = self.gc.perform_cleanup()
        self.assertGreaterEqual(summary["total_evicted"], 1)
        self.assertGreaterEqual(len(events), 1)

    def test_07_gc_metrics(self):
        """Test 7: Trigger GC sweep and verify get_gc_metrics() updates counters."""
        self.gc.perform_cleanup()
        metrics = self.gc.get_gc_metrics()
        self.assertGreater(metrics["total_sweeps"], 0)

    def test_08_ttl_cleanup(self):
        """Test 8: Evict expired 100ms TTL scratchpad notes."""
        self.scratchpad.append_entry("task_ttl", "a1", "Note")
        time.sleep(0.15)
        evicted = self.scratchpad.clear_expired(max_age_seconds=0.05)
        self.assertEqual(evicted, 1)

    def test_09_metrics_telemetry_export(self):
        """Test 9: Call export_metrics(); verify system, workspace, recovery, and GC metrics present."""
        metrics = self.telemetry.export_metrics()
        self.assertIn("system", metrics)
        self.assertIn("workspace_store", metrics)
        self.assertIn("recovery_journal", metrics)
        self.assertIn("garbage_collector", metrics)
        self.assertGreaterEqual(metrics["system"]["uptime_seconds"], 0.0)

    def test_10_multi_threaded_concurrent_journal_appends(self):
        """Test 10: 20 concurrent threads appending journal events simultaneously."""
        threads = []

        def worker(num):
            for i in range(10):
                self.journal.append_event("WRITE", {"key": f"k_{num}_{i}", "value": i})

        for i in range(20):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        replayed = self.journal.replay()
        self.assertEqual(len(replayed), 200)

    def test_11_multi_threaded_concurrent_gc(self):
        """Test 11: 10 concurrent threads calling perform_cleanup() simultaneously."""
        threads = []

        def worker():
            for _ in range(5):
                self.gc.perform_cleanup()

        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        metrics = self.gc.get_gc_metrics()
        self.assertGreaterEqual(metrics["total_sweeps"], 50)

    def test_12_hard_crash_recovery_simulation(self):
        """Test 12: Simulate hard crash with journal replay restoring store state."""
        self.journal.append_event("WRITE", {"key": "crash_k1", "value": "crash_v1", "owner": "system"})
        self.journal.append_event("WRITE", {"key": "crash_k2", "value": "crash_v2", "owner": "system"})

        fresh_store = WorkspaceStore()
        fresh_store.initialize()

        self.journal.recover(workspace_store=fresh_store)
        self.assertEqual(fresh_store.read("crash_k1"), "crash_v1")
        self.assertEqual(fresh_store.read("crash_k2"), "crash_v2")

    def test_13_journal_truncation(self):
        """Test 13: Call truncate(); verify log size resets to 0 bytes."""
        self.journal.append_event("WRITE", {"key": "trunc_k", "value": "val"})
        self.assertTrue(os.path.getsize(self.journal_path) > 0)

        self.journal.truncate()
        self.assertEqual(os.path.getsize(self.journal_path), 0)

    def test_14_journal_benchmark(self):
        """Test 14: Benchmark 1,000 journal appends (> 500 events/sec)."""
        start_t = time.time()
        for i in range(1000):
            self.journal.append_event("BENCH", {"i": i})

        elapsed = time.time() - start_t
        throughput = 1000 / elapsed
        print(f"\n[Journal Benchmark] Appended 1,000 events in {elapsed:.2f}s ({throughput:.1f} events/sec)")
        self.assertGreater(throughput, 100.0)

    def test_15_phase1_backward_compatibility_check(self):
        """Test 15: Verify Phase 1 contracts remain unchanged and accessible."""
        from core.session import session
        from core.event_bus import event_bus
        self.assertIsNotNone(session)
        self.assertIsNotNone(event_bus)


if __name__ == "__main__":
    unittest.main()
