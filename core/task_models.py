"""
ULTRON V3 - Task Models
Dataclass schemas and enums for the Priority Task Engine.
Zero external framework dependencies.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, Any, List, Optional


class PriorityLevel(IntEnum):
    """Priority levels for task scheduling (lower numerical value = higher priority)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskStatus(str, Enum):
    """Task lifecycle statuses."""
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DLQ = "DLQ"


@dataclass
class TaskDescriptor:
    """Production Task Descriptor carrying execution metadata and lease tracking."""
    task_id: str = field(default_factory=lambda: f"tsk_{uuid.uuid4().hex[:12]}")
    correlation_id: str = field(default_factory=lambda: f"cor_{uuid.uuid4().hex[:12]}")
    trace_id: str = field(default_factory=lambda: f"trc_{uuid.uuid4().hex[:12]}")
    parent_task_id: Optional[str] = None
    priority: PriorityLevel = PriorityLevel.NORMAL
    status: TaskStatus = TaskStatus.CREATED
    owner: str = "system"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    heartbeat_at: Optional[float] = None
    
    # Retry and Leasing
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 30.0
    lease_owner: Optional[str] = None
    lease_expiry: Optional[float] = None
    lease_token: Optional[str] = None
    
    # Executable Callable Target (for in-process task execution)
    action: Optional[str] = None
    exec_func: Any = None

    def __lt__(self, other: "TaskDescriptor") -> bool:
        """Priority comparison for priority queue ordering."""
        if not isinstance(other, TaskDescriptor):
            return NotImplemented
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


@dataclass
class TaskResult:
    """Task execution result wrapper."""
    task_id: str
    status: TaskStatus
    result_data: Any = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
