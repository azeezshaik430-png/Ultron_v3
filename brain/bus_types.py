"""
ULTRON V3 - Agent Memory Bus Types
Dataclass schemas and enums for the Agent Memory Bus infrastructure.
Pure data structures ONLY - zero business logic.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, Any, List, Optional


class MessagePriority(IntEnum):
    """Priority levels for bus messages (lower numerical value = higher priority)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class DeliveryStatus(str, Enum):
    """Message delivery status lifecycle."""
    QUEUED = "QUEUED"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    NACKNOWLEDGED = "NACKNOWLEDGED"
    EXPIRED = "EXPIRED"
    DLQ = "DLQ"


class AgentStatus(str, Enum):
    """Subagent operational health status."""
    OFFLINE = "OFFLINE"
    INITIALIZING = "INITIALIZING"
    ONLINE = "ONLINE"
    BUSY = "BUSY"
    UNHEALTHY = "UNHEALTHY"
    DEGRADED = "DEGRADED"


class CircuitBreakerState(str, Enum):
    """Health monitor circuit breaker state."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class ArtifactMetadata:
    """Metadata schema for artifacts created by subagents."""
    artifact_id: str = field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    task_id: str = ""
    file_path: str = ""
    mime_type: str = "text/plain"
    size_bytes: int = 0
    sha256_hash: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessage:
    """Message envelope schema for inter-agent pub/sub and P2P communication."""
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    trace_id: str = field(default_factory=lambda: f"trc_{uuid.uuid4().hex[:12]}")
    correlation_id: str = field(default_factory=lambda: f"cor_{uuid.uuid4().hex[:12]}")
    sender_id: str = "system"
    recipient_id: Optional[str] = None
    topic: str = "general"
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    ttl_ms: int = 30000
    workspace_version: int = 1
    agent_ownership: str = "system"
    payload: Dict[str, Any] = field(default_factory=dict)
    artifact_metadata: Optional[ArtifactMetadata] = None
    delivery_status: DeliveryStatus = DeliveryStatus.QUEUED
    retry_count: int = 0


@dataclass
class WorkspaceEntry:
    """Shared workspace store key-value entry with version locking."""
    key: str
    value: Any
    version: int = 1
    task_id: str = ""
    owner_agent: str = "system"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ScratchpadEntry:
    """Task-scoped transient scratchpad note."""
    task_id: str
    agent_id: str
    entry_text: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentManifest:
    """Manifest describing a registered subagent's identity and capabilities."""
    agent_id: str
    name: str
    version: str = "1.0.0"
    capabilities: List[str] = field(default_factory=list)
    supported_skills: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BusStatistics:
    """Agent Memory Bus telemetry statistics container."""
    agent_latency_ms: float = 0.0
    task_latency_ms: float = 0.0
    queue_depth: int = 0
    dlq_size: int = 0
    workspace_bytes: int = 0
    scratchpad_bytes: int = 0
    artifact_count: int = 0
    total_retries: int = 0
    total_failures: int = 0
    throughput_per_sec: float = 0.0
    cpu_utilization: float = 0.0
    ram_usage_mb: float = 0.0
    dropped_messages: int = 0
    workspace_version: int = 1
    transactions_per_sec: float = 0.0
    ack_latency_ms: float = 0.0
    nack_count: int = 0
    duplicate_suppression_count: int = 0
