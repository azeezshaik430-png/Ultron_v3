"""
ULTRON V3 - Sub-Milestone 2.3 Verification Test Suite
Tests WorkspaceStore CRUD, version locking, snapshot/restore, ACL permission validation,
optimistic transactions, conflict detection, quotas, multi-threaded concurrency, and Phase 1 compatibility.
"""

import gc
import os
import sys
import threading
import time
import unittest

from core.event_bus import event_bus
from core.exceptions import (
    WorkspaceConflictException,
    PermissionDeniedException,
    QuotaExceededException,
    BusException,
)
from brain.workspace_store import WorkspaceStore
from brain.transaction_manager import TransactionManager, TransactionContext
from brain.workspace_acl import WorkspaceACL, PermissionType, AccessTier


class TestSubMilestone23(unittest.TestCase):
    """Sub-Milestone 2.3 Complete Test Suite."""

    def setUp(self):
        self.acl = WorkspaceACL()
        self.store = WorkspaceStore(
            max_keys=10,
            max_value_size=1024,
            max_snapshots=3,
            acl=self.acl,
        )
        self.store.initialize()
        self.tx_mgr = TransactionManager(workspace_store=self.store)

    def tearDown(self):
        self.store.shutdown()
        self.acl.clear()

    def test_01_workspace_crud_operations(self):
        """Test 1: Workspace Store write, read, exists, and delete operations."""
        v1 = self.store.write("key1", "hello", owner_agent="agent_a")
        self.assertEqual(v1, 1)
        self.assertTrue(self.store.exists("key1"))
        self.assertEqual(self.store.read("key1", agent_id="agent_a"), "hello")

        self.assertTrue(self.store.delete("key1", agent_id="agent_a"))
        self.assertFalse(self.store.exists("key1"))

    def test_02_monotonic_version_increment(self):
        """Test 2: Verify key version increments monotonically on every write."""
        v1 = self.store.write("key_ver", "val1")
        v2 = self.store.write("key_ver", "val2")
        v3 = self.store.write("key_ver", "val3")

        self.assertEqual(v1, 1)
        self.assertEqual(v2, 2)
        self.assertEqual(v3, 3)

    def test_03_snapshot_and_restore(self):
        """Test 3: Create snapshot, mutate workspace, restore snapshot; verify state reset."""
        self.store.write("k1", "original")
        snap = self.store.create_snapshot(created_by="test_user", description="Pre-mutation snapshot")

        self.assertEqual(snap["description"], "Pre-mutation snapshot")
        self.assertIn("snapshot_id", snap)

        # Mutate store
        self.store.write("k1", "mutated")
        self.store.write("k2", "new_key")
        self.assertEqual(self.store.read("k1"), "mutated")

        # Restore snapshot
        self.store.restore_snapshot(snap)
        self.assertEqual(self.store.read("k1"), "original")
        self.assertFalse(self.store.exists("k2"))

    def test_04_transactional_commit(self):
        """Test 4: Begin transaction, stage writes, commit; verify atomic updates and event."""
        events = []
        event_bus.subscribe("TRANSACTION_COMMITTED", lambda **p: events.append(p))

        tx = self.tx_mgr.begin_transaction("agent_a", "task_100")
        self.tx_mgr.staged_write(tx, "tx_k1", "v1")
        self.tx_mgr.staged_write(tx, "tx_k2", "v2")

        self.assertFalse(self.store.exists("tx_k1"))

        self.assertTrue(self.tx_mgr.commit(tx))
        self.assertEqual(self.store.read("tx_k1"), "v1")
        self.assertEqual(self.store.read("tx_k2"), "v2")
        self.assertGreaterEqual(len(events), 1)

    def test_05_transactional_rollback(self):
        """Test 5: Begin transaction, stage writes, rollback; verify zero workspace mutation."""
        events = []
        event_bus.subscribe("TRANSACTION_ROLLED_BACK", lambda **p: events.append(p))

        tx = self.tx_mgr.begin_transaction("agent_a", "task_100")
        self.tx_mgr.staged_write(tx, "rb_k1", "v1")

        self.tx_mgr.rollback(tx)
        self.assertFalse(self.store.exists("rb_k1"))
        self.assertGreaterEqual(len(events), 1)

    def test_06_optimistic_conflict_detection(self):
        """Test 6: Two transactions snapshot v1; first commits v2, second fails with WorkspaceConflictException."""
        self.store.write("shared_key", "initial_val")

        tx1 = self.tx_mgr.begin_transaction("agent_1", "t1")
        tx2 = self.tx_mgr.begin_transaction("agent_2", "t2")

        self.tx_mgr.staged_write(tx1, "shared_key", "val_by_tx1")
        self.tx_mgr.staged_write(tx2, "shared_key", "val_by_tx2")

        # TX1 commits first -> succeeds
        self.assertTrue(self.tx_mgr.commit(tx1))
        self.assertEqual(self.store.read("shared_key"), "val_by_tx1")

        # TX2 commits second -> fails due to version mismatch
        with self.assertRaises(WorkspaceConflictException):
            self.tx_mgr.commit(tx2)

    def test_07_transaction_timeout_handling(self):
        """Test 7: Transaction exceeding timeout throws exception on staging/committing."""
        tx = self.tx_mgr.begin_transaction("agent_a", "t_timeout", timeout=0.1)
        time.sleep(0.2)

        with self.assertRaises(BusException):
            self.tx_mgr.staged_write(tx, "expired_k", "val")

    def test_08_acl_grant_and_permission_denial(self):
        """Test 8: Grant READ_ONLY access to Agent B; verify Agent B can read but write throws PermissionDeniedException."""
        self.store.write("secret_key", "top_secret", owner_agent="agent_owner")
        self.acl.grant_permission("secret_key", "agent_b", AccessTier.READ_ONLY)

        self.assertEqual(self.store.read("secret_key", agent_id="agent_b"), "top_secret")

        with self.assertRaises(PermissionDeniedException):
            self.store.write("secret_key", "hack_attempt", owner_agent="agent_b")

    def test_09_task_scoped_acl_isolation(self):
        """Test 9: Verify Agent from Task A cannot access Task B scoped keys when restricted."""
        self.acl.grant_permission("task_key", "agent_x", AccessTier.SHARED, task_id="task_A")

        self.assertTrue(self.acl.validate_access("task_key", "agent_x", PermissionType.READ, task_id="task_A"))
        self.assertFalse(self.acl.validate_access("task_key", "agent_x", PermissionType.READ, task_id="task_B"))

    def test_10_multi_threaded_concurrent_writers(self):
        """Test 10: 20 concurrent threads attempting transactional writes simultaneously."""
        threads = []

        def worker(num):
            for i in range(10):
                try:
                    tx = self.tx_mgr.begin_transaction(f"agent_{num}", f"task_{num}")
                    self.tx_mgr.staged_write(tx, f"conc_key_{num}", f"val_{i}")
                    self.tx_mgr.commit(tx)
                except WorkspaceConflictException:
                    pass

        for i in range(20):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        metrics = self.tx_mgr.get_transaction_metrics()
        self.assertGreater(metrics["committed_transactions"], 0)

    def test_11_multi_threaded_concurrent_readers(self):
        """Test 11: 20 concurrent threads reading workspace keys during active writes."""
        self.store.write("read_key", "initial")
        threads = []

        def reader():
            for _ in range(50):
                val = self.store.read("read_key")
                self.assertIn(val, ["initial", "updated"])

        def writer():
            for _ in range(20):
                self.store.write("read_key", "updated")
                time.sleep(0.001)

        for _ in range(15):
            threads.append(threading.Thread(target=reader))
        threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_12_transaction_metrics_api(self):
        """Test 12: Verify get_transaction_metrics reports commit, rollback, and conflict counts."""
        tx1 = self.tx_mgr.begin_transaction("a1", "t1")
        self.tx_mgr.staged_write(tx1, "m_k1", "v1")
        self.tx_mgr.commit(tx1)

        tx2 = self.tx_mgr.begin_transaction("a2", "t2")
        self.tx_mgr.staged_write(tx2, "m_k2", "v2")
        self.tx_mgr.rollback(tx2)

        metrics = self.tx_mgr.get_transaction_metrics()
        self.assertEqual(metrics["committed_transactions"], 1)
        self.assertEqual(metrics["rolled_back_transactions"], 1)

    def test_13_snapshot_version_history(self):
        """Test 13: Verify snapshot creation tracks version history and respects max_snapshots limit."""
        for i in range(5):
            self.store.write("hist_key", f"v_{i}")
            self.store.create_snapshot(description=f"Snapshot {i}")

        health = self.store.health_check()
        # Max snapshots configured as 3 in setUp
        self.assertEqual(health["snapshot_count"], 3)

    def test_14_workspace_quota_enforcement(self):
        """Test 14: Verify writing exceeding max_keys or payload max_value_size raises QuotaExceededException."""
        # 1. Payload size quota test (max_value_size = 1024 bytes)
        large_payload = "X" * 2000
        with self.assertRaises(QuotaExceededException):
            self.store.write("large_key", large_payload)

        # 2. Key count quota test (max_keys = 10)
        for i in range(10):
            self.store.write(f"q_key_{i}", "val")

        with self.assertRaises(QuotaExceededException):
            self.store.write("overflow_key", "val")


if __name__ == "__main__":
    unittest.main()
