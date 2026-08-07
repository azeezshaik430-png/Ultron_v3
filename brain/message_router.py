"""
ULTRON V3 - Reliable Agent Message Router
Point-to-point and pub/sub message router with ACK/NACK, exponential retries, DLQ, duplicate suppression, and priority queues.
Zero external framework dependencies.
"""

import hashlib
import json
import threading
import time
from queue import PriorityQueue, Empty
from typing import Dict, Any, List, Optional, Set

from core.config import config
from core.event_bus import event_bus
from core.interfaces import IService
from core.logger import logger
from brain.bus_types import AgentMessage, DeliveryStatus, MessagePriority


class AgentMessageRouter(IService):
    """
    Reliable Agent Message Router.
    
    Purpose:
    - Provides thread-safe point-to-point and topic message delivery with delivery guarantees.
    
    Responsibilities:
    - Priority queueing based on MessagePriority (CRITICAL, HIGH, NORMAL, LOW).
    - SHA-256 payload hash duplicate suppression (idempotency).
    - Delivery ACK/NACK state handling with exponential backoff retries.
    - Dead Letter Queueing (DLQ) for exhausted retries or TTL expired messages.
    - Publishes router lifecycle events over Phase 1 EventBus.
    
    Thread-Safety:
    - Inbox queues use Python thread-safe PriorityQueue. Master indexes use RLock.
    """

    def __init__(
        self,
        max_retries: Optional[int] = None,
        default_ttl_ms: Optional[int] = None,
        backoff_base: Optional[float] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.max_retries = max_retries or getattr(config, "MESSAGE_ROUTER_MAX_RETRIES", 3)
        self.default_ttl_ms = default_ttl_ms or getattr(config, "MESSAGE_ROUTER_DEFAULT_TTL_MS", 30000)
        self.backoff_base = backoff_base or getattr(config, "MESSAGE_ROUTER_BACKOFF_BASE", 0.1)

        # Agent Inbox Queues: agent_id -> PriorityQueue
        self._inboxes: Dict[str, PriorityQueue] = {}
        # Pending Outbox tracking: message_id -> AgentMessage
        self._outbox: Dict[str, AgentMessage] = {}
        # Dead Letter Queue
        self._dlq: List[AgentMessage] = []
        # Bloom/Hash Set for duplicate payload suppression (recent 1000 hashes)
        self._payload_hashes: Set[str] = set()
        
        # Telemetry metrics
        self._total_sent = 0
        self._total_delivered = 0
        self._total_acked = 0
        self._total_nacked = 0
        self._total_expired = 0
        self._duplicate_suppression_count = 0

        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize message router."""
        with self._lock:
            if self._is_initialized:
                return
            self._is_initialized = True
            logger.info("[AgentMessageRouter] Reliable Message Router initialized.")

    def shutdown(self) -> None:
        """Cleanly release message router state."""
        with self._lock:
            self._inboxes.clear()
            self._outbox.clear()
            self._dlq.clear()
            self._payload_hashes.clear()
            self._is_initialized = False
            logger.info("[AgentMessageRouter] Reliable Message Router shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return message router health status."""
        with self._lock:
            total_queued = sum(q.qsize() for q in self._inboxes.values())
            return {
                "status": "HEALTHY" if self._is_initialized else "STOPPED",
                "healthy": self._is_initialized,
                "active_inboxes_count": len(self._inboxes),
                "total_queued_messages": total_queued,
                "dlq_size": len(self._dlq),
                "metrics": self.get_router_metrics(),
            }

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration parameters."""
        with self._lock:
            if "max_retries" in config_data:
                self.max_retries = int(config_data["max_retries"])
            if "default_ttl_ms" in config_data:
                self.default_ttl_ms = int(config_data["default_ttl_ms"])
            if "backoff_base" in config_data:
                self.backoff_base = float(config_data["backoff_base"])

    def send_message(self, envelope: AgentMessage) -> str:
        """
        Send a message envelope with priority routing and SHA-256 duplicate suppression.
        
        Args:
            envelope (AgentMessage): Message envelope container.
            
        Returns:
            str: Assigned message ID string.
        """
        with self._lock:
            # 1. Duplicate Suppression Check (SHA-256 hash of payload)
            payload_str = json.dumps(envelope.payload, sort_keys=True)
            payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            if payload_hash in self._payload_hashes:
                self._duplicate_suppression_count += 1
                logger.warning(f"[AgentMessageRouter] Suppressed duplicate message payload hash '{payload_hash[:8]}'.")
                return envelope.message_id

            self._payload_hashes.add(payload_hash)
            if len(self._payload_hashes) > 1000:
                self._payload_hashes.pop()

            recipient = envelope.recipient_id or "broadcast"
            if recipient not in self._inboxes:
                self._inboxes[recipient] = PriorityQueue()

            envelope.delivery_status = DeliveryStatus.QUEUED
            self._outbox[envelope.message_id] = envelope
            
            # Wrap in priority queue item: (priority_int, timestamp, envelope)
            priority_weight = int(envelope.priority)
            self._inboxes[recipient].put((priority_weight, envelope.timestamp, envelope))
            
            self._total_sent += 1
            event_bus.publish("MESSAGE_SENT", message_id=envelope.message_id, sender=envelope.sender_id, recipient=recipient, topic=envelope.topic)
            return envelope.message_id

    def receive_message(self, agent_id: str, timeout: float = 0.1) -> Optional[AgentMessage]:
        """
        Receive top priority message for a subagent inbox with TTL expiration check.
        
        Args:
            agent_id (str): Subagent ID checking inbox.
            timeout (float): Max wait timeout in seconds.
            
        Returns:
            Optional[AgentMessage]: Next valid envelope, or None if empty.
        """
        inbox = None
        with self._lock:
            inbox = self._inboxes.get(agent_id) or self._inboxes.get("broadcast")

        if not inbox:
            return None

        try:
            priority_weight, msg_time, envelope = inbox.get(timeout=timeout)
        except Empty:
            return None

        now = time.time()
        ttl_sec = (envelope.ttl_ms or self.default_ttl_ms) / 1000.0

        with self._lock:
            # Check TTL Expiration
            if (now - envelope.timestamp) > ttl_sec:
                envelope.delivery_status = DeliveryStatus.EXPIRED
                self._dlq.append(envelope)
                self._outbox.pop(envelope.message_id, None)
                self._total_expired += 1
                event_bus.publish("MESSAGE_EXPIRED", message_id=envelope.message_id, agent_id=agent_id)
                logger.warning(f"[AgentMessageRouter] Message '{envelope.message_id}' expired in inbox.")
                return None

            envelope.delivery_status = DeliveryStatus.DELIVERED
            self._total_delivered += 1
            event_bus.publish("MESSAGE_DELIVERED", message_id=envelope.message_id, agent_id=agent_id)
            return envelope

    def acknowledge_message(self, message_id: str) -> bool:
        """
        Acknowledge (ACK) successful processing of a message.
        
        Args:
            message_id (str): Target message ID.
            
        Returns:
            bool: True if ACK succeeded.
        """
        with self._lock:
            envelope = self._outbox.pop(message_id, None)
            if envelope:
                envelope.delivery_status = DeliveryStatus.ACKNOWLEDGED
                self._total_acked += 1
                event_bus.publish("MESSAGE_ACKNOWLEDGED", message_id=message_id)
                return True
            return False

    def negative_acknowledge(self, message_id: str, reason: str = "") -> bool:
        """
        Negative acknowledge (NACK) message processing with retry or DLQ routing.
        
        Args:
            message_id (str): Target message ID.
            reason (str): NACK failure explanation.
            
        Returns:
            bool: True if NACK processed.
        """
        with self._lock:
            envelope = self._outbox.get(message_id)
            if not envelope:
                return False

            self._total_nacked += 1
            envelope.retry_count += 1
            event_bus.publish("MESSAGE_NACKNOWLEDGED", message_id=message_id, reason=reason, retries=envelope.retry_count)

            if envelope.retry_count < self.max_retries:
                envelope.delivery_status = DeliveryStatus.QUEUED
                backoff_sec = self.backoff_base * (2 ** (envelope.retry_count - 1))
                
                # Re-queue in priority queue after backoff
                def requeue_task():
                    time.sleep(backoff_sec)
                    with self._lock:
                        recipient = envelope.recipient_id or "broadcast"
                        if recipient in self._inboxes:
                            self._inboxes[recipient].put((int(envelope.priority), time.time(), envelope))

                threading.Thread(target=requeue_task, daemon=True).start()
                return True
            else:
                envelope.delivery_status = DeliveryStatus.DLQ
                self._dlq.append(envelope)
                self._outbox.pop(message_id, None)
                event_bus.publish("MESSAGE_DLQ", message_id=message_id, reason="Max retries exhausted")
                logger.error(f"[AgentMessageRouter] Message '{message_id}' moved to DLQ after {envelope.retry_count} retries.")
                return True

    def get_dlq_messages(self) -> List[AgentMessage]:
        """Return copies of all messages in the Dead Letter Queue."""
        with self._lock:
            return list(self._dlq)

    def get_router_metrics(self) -> Dict[str, Any]:
        """
        Return telemetry metrics summary.
        
        Returns:
            Dict[str, Any]: Telemetry metrics summary dictionary.
        """
        with self._lock:
            return {
                "total_sent": self._total_sent,
                "total_delivered": self._total_delivered,
                "total_acked": self._total_acked,
                "total_nacked": self._total_nacked,
                "total_expired": self._total_expired,
                "dlq_size": len(self._dlq),
                "duplicate_suppression_count": self._duplicate_suppression_count,
            }
