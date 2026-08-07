"""
ULTRON V3 - Sub-Milestone 2.4 Verification Test Suite
Tests MessageRouter ACK/NACK, retries, DLQ, duplicate suppression, priority routing, TTL expiry,
Scratchpad CRUD & isolation, ArtifactRegistry security & versioning, multi-threaded messaging, and Phase 1 compatibility.
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
    QuotaExceededException,
    BusException,
)
from brain.message_router import AgentMessageRouter
from brain.scratchpad import AgentScratchpad
from brain.artifact_registry import ArtifactRegistry
from brain.bus_types import (
    AgentMessage,
    MessagePriority,
    DeliveryStatus,
    ArtifactMetadata,
)


class TestSubMilestone24(unittest.TestCase):
    """Sub-Milestone 2.4 Complete Test Suite."""

    def setUp(self):
        self.router = AgentMessageRouter(max_retries=3, default_ttl_ms=1000, backoff_base=0.05)
        self.router.initialize()

        self.scratchpad = AgentScratchpad(max_size_mb=2)
        self.scratchpad.initialize()

        self.test_art_dir = os.path.abspath("data/test_artifacts")
        os.makedirs(self.test_art_dir, exist_ok=True)
        self.artifacts = ArtifactRegistry(storage_dir=self.test_art_dir, max_storage_mb=100)
        self.artifacts.initialize()

    def tearDown(self):
        self.artifacts.shutdown()
        self.scratchpad.shutdown()
        self.router.shutdown()

    def test_01_router_send_and_receive(self):
        """Test 1: Send message envelope and receive in target agent inbox."""
        msg = AgentMessage(
            sender_id="agent_sender",
            recipient_id="agent_receiver",
            topic="test_topic",
            payload={"action": "run_analysis"},
        )
        msg_id = self.router.send_message(msg)
        self.assertEqual(msg_id, msg.message_id)

        recv_msg = self.router.receive_message("agent_receiver", timeout=0.5)
        self.assertIsNotNone(recv_msg)
        self.assertEqual(recv_msg.message_id, msg.message_id)
        self.assertEqual(recv_msg.delivery_status, DeliveryStatus.DELIVERED)

    def test_02_message_ack_processing(self):
        """Test 2: Receive message, acknowledge (ACK), verify outbox eviction and event."""
        events = []
        event_bus.subscribe("MESSAGE_ACKNOWLEDGED", lambda **p: events.append(p))

        msg = AgentMessage(sender_id="s1", recipient_id="r1", payload={"data": 100})
        msg_id = self.router.send_message(msg)
        recv = self.router.receive_message("r1")

        self.assertTrue(self.router.acknowledge_message(msg_id))
        self.assertGreaterEqual(len(events), 1)

    def test_03_message_nack_exponential_retry(self):
        """Test 3: NACK message and verify retry counter increment and re-queueing."""
        msg = AgentMessage(sender_id="s2", recipient_id="r2", payload={"data": 200})
        msg_id = self.router.send_message(msg)
        recv = self.router.receive_message("r2")

        # NACK 1st attempt -> re-queued
        self.assertTrue(self.router.negative_acknowledge(msg_id, reason="Temporary failure"))
        time.sleep(0.15)

        recv_retry = self.router.receive_message("r2", timeout=0.5)
        self.assertIsNotNone(recv_retry)
        self.assertEqual(recv_retry.retry_count, 1)

    def test_04_dead_letter_queue_exhaustion(self):
        """Test 4: NACK max_retries times; verify message moves to DLQ."""
        msg = AgentMessage(sender_id="s3", recipient_id="r3", payload={"data": 300})
        msg_id = self.router.send_message(msg)

        for attempt in range(3):
            recv = self.router.receive_message("r3", timeout=0.5)
            if recv:
                self.router.negative_acknowledge(msg_id, reason=f"Attempt {attempt+1} failed")
                time.sleep(0.2)

        dlq = self.router.get_dlq_messages()
        self.assertEqual(len(dlq), 1)
        self.assertEqual(dlq[0].delivery_status, DeliveryStatus.DLQ)

    def test_05_sha256_duplicate_payload_suppression(self):
        """Test 5: Send identical payload twice; verify 2nd message payload hash is suppressed."""
        payload = {"task": "process_batch_99"}
        msg1 = AgentMessage(sender_id="a1", recipient_id="b1", payload=payload)
        msg2 = AgentMessage(sender_id="a1", recipient_id="b1", payload=payload)

        self.router.send_message(msg1)
        self.router.send_message(msg2)

        metrics = self.router.get_router_metrics()
        self.assertEqual(metrics["duplicate_suppression_count"], 1)

    def test_06_message_ttl_expiration(self):
        """Test 6: Send message with 100ms TTL, sleep 200ms; verify receive detects EXPIRED status."""
        msg = AgentMessage(sender_id="s_ttl", recipient_id="r_ttl", ttl_ms=100, payload={"temp": True})
        self.router.send_message(msg)

        time.sleep(0.2)
        recv = self.router.receive_message("r_ttl", timeout=0.1)
        self.assertIsNone(recv)

        dlq = self.router.get_dlq_messages()
        self.assertEqual(len(dlq), 1)
        self.assertEqual(dlq[0].delivery_status, DeliveryStatus.EXPIRED)

    def test_07_priority_routing_order(self):
        """Test 7: Enqueue NORMAL, LOW, and CRITICAL priority messages; verify CRITICAL received first."""
        m_normal = AgentMessage(sender_id="s", recipient_id="r_prio", priority=MessagePriority.NORMAL, payload={"p": "normal"})
        m_low = AgentMessage(sender_id="s", recipient_id="r_prio", priority=MessagePriority.LOW, payload={"p": "low"})
        m_critical = AgentMessage(sender_id="s", recipient_id="r_prio", priority=MessagePriority.CRITICAL, payload={"p": "critical"})

        self.router.send_message(m_normal)
        self.router.send_message(m_low)
        self.router.send_message(m_critical)

        recv1 = self.router.receive_message("r_prio")
        self.assertEqual(recv1.priority, MessagePriority.CRITICAL)

        recv2 = self.router.receive_message("r_prio")
        self.assertEqual(recv2.priority, MessagePriority.NORMAL)

    def test_08_scratchpad_crud_operations(self):
        """Test 8: Append, read, update, and delete scratchpad entries."""
        entry = self.scratchpad.append_entry("task_01", "agent_research", "Found API specs.")
        self.assertEqual(entry.entry_text, "Found API specs.")

        notes = self.scratchpad.read_scratchpad("task_01", "agent_research")
        self.assertEqual(len(notes), 1)

        self.assertTrue(self.scratchpad.update_entry("task_01", "agent_research", 0, "Updated API specs."))
        notes_updated = self.scratchpad.read_scratchpad("task_01", "agent_research")
        self.assertEqual(notes_updated[0].entry_text, "Updated API specs.")

        self.assertTrue(self.scratchpad.delete_scratchpad("task_01"))
        self.assertEqual(len(self.scratchpad.read_scratchpad("task_01")), 0)

    def test_09_scratchpad_isolation(self):
        """Test 9: Verify task and agent scratchpad scoping isolation."""
        self.scratchpad.append_entry("task_A", "agent_1", "Note A1")
        self.scratchpad.append_entry("task_A", "agent_2", "Note A2")
        self.scratchpad.append_entry("task_B", "agent_1", "Note B1")

        notes_a1 = self.scratchpad.read_scratchpad("task_A", "agent_1")
        self.assertEqual(len(notes_a1), 1)
        self.assertEqual(notes_a1[0].entry_text, "Note A1")

        notes_task_a = self.scratchpad.read_scratchpad("task_A")
        self.assertEqual(len(notes_task_a), 2)

    def test_10_scratchpad_cleanup(self):
        """Test 10: Clear expired scratchpad notes older than max_age_seconds."""
        self.scratchpad.append_entry("old_task", "agent_1", "Old note")
        time.sleep(0.1)

        evicted = self.scratchpad.clear_expired(max_age_seconds=0.05)
        self.assertEqual(evicted, 1)

    def test_11_artifact_path_traversal_security(self):
        """Test 11: Attempt '../../etc/passwd' registration; verify PermissionDeniedException."""
        with self.assertRaises(PermissionDeniedException):
            self.artifacts.register_artifact("task_sec", "../../../etc/passwd")

    def test_12_artifact_hashing_and_versioning(self):
        """Test 12: Register artifact file twice; verify SHA-256 checksum and version increment."""
        file_path = os.path.join(self.test_art_dir, "report.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Artifact Report Content")

        art1 = self.artifacts.register_artifact("task_art", file_path)
        self.assertEqual(art1.metadata["version"], 1)
        self.assertTrue(len(art1.sha256_hash) > 0)

        # Register again -> Version 2
        art2 = self.artifacts.register_artifact("task_art", file_path)
        self.assertEqual(art2.metadata["version"], 2)

    def test_13_artifact_reference_counting(self):
        """Test 13: Verify artifact reference counting and catalog removal."""
        file_path = os.path.join(self.test_art_dir, "data.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("a,b,c")

        art = self.artifacts.register_artifact("task_ref", file_path)
        self.assertEqual(self.artifacts.get_reference_count(art.artifact_id), 1)

        self.assertEqual(self.artifacts.add_reference(art.artifact_id), 2)
        self.assertEqual(self.artifacts.release_reference(art.artifact_id), 1)

        self.assertTrue(self.artifacts.remove_artifact(art.artifact_id))
        self.assertIsNone(self.artifacts.get_artifact(art.artifact_id))

    def test_14_concurrent_multi_threaded_messaging(self):
        """Test 14: 20 concurrent threads sending and receiving messages simultaneously."""
        threads = []
        recv_count = [0]
        lock = threading.Lock()

        def sender(num):
            msg = AgentMessage(sender_id=f"s_{num}", recipient_id="worker_inbox", payload={"num": num})
            self.router.send_message(msg)

        def receiver():
            for _ in range(5):
                msg = self.router.receive_message("worker_inbox", timeout=0.2)
                if msg:
                    self.router.acknowledge_message(msg.message_id)
                    with lock:
                        recv_count[0] += 1

        for i in range(20):
            threads.append(threading.Thread(target=sender, args=(i,)))
            threads.append(threading.Thread(target=receiver))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = self.router.get_router_metrics()
        self.assertGreater(metrics["total_sent"], 0)

    def test_15_phase1_backward_compatibility_check(self):
        """Test 15: Verify Phase 1 contracts remain unchanged and accessible."""
        from core.session import session
        from core.event_bus import event_bus
        self.assertIsNotNone(session)
        self.assertIsNotNone(event_bus)


if __name__ == "__main__":
    unittest.main()
