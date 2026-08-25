"""
ULTRON V3 - Base Ultron Agent Framework
Master foundation class for all Phase 2B Ultron domain agents.
Integrates Phase 2A AgentMemoryBus, ServiceManager, HealthMonitor, WorkspaceACL, Scratchpad, and Telemetry.
"""

import threading
import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from core.interfaces import IService
from core.logger import logger
from agents.base_agent import BaseAgent
from brain.bus_types import (
    AgentManifest,
    AgentMessage,
    AgentStatus,
    MessagePriority,
    ArtifactMetadata,
)
from brain.workspace_acl import AccessTier


class BaseUltronAgent(BaseAgent, IService, ABC):
    """
    Unified Base Class for all Phase 2B Ultron Agents.
    
    Purpose:
    - Provides standardized agent identity, manifest, lifecycle management, health heartbeats,
      WorkspaceACL access control, bus messaging, scratchpad logging, and telemetry metrics.
      
    Responsibilities:
    - Registers agent manifest with AgentMemoryBus during initialize().
    - Manages agent health status (OFFLINE, INITIALIZING, ONLINE, BUSY, UNHEALTHY, DEGRADED).
    - Runs a daemon thread periodically sending heartbeat signals to HealthMonitor.
    - Exposes thread-safe task execution, message send/receive, scratchpad logging, and workspace store operations.
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        capabilities: Optional[List[str]] = None,
        supported_skills: Optional[List[str]] = None,
        bus: Optional[Any] = None,
        version: str = "1.0.0",
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.version = version
        self.capabilities = capabilities or []
        self.supported_skills = supported_skills or []
        self.bus = bus

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_interval = 5.0

        self.status = AgentStatus.OFFLINE
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, Any] = {
            "tasks_executed": 0,
            "tasks_failed": 0,
            "total_execution_time_ms": 0.0,
            "messages_sent": 0,
            "messages_received": 0,
        }
        self._is_initialized = False

    def get_manifest(self) -> AgentManifest:
        """Return agent manifest descriptor."""
        return AgentManifest(
            agent_id=self.agent_id,
            name=self.name,
            version=self.version,
            capabilities=list(self.capabilities),
            supported_skills=list(self.supported_skills),
            metadata={"description": self.description},
        )

    def initialize(self) -> None:
        """Initialize agent, register manifest with AgentMemoryBus, and start heartbeat loop."""
        with self._lock:
            if self._is_initialized:
                return
            self.status = AgentStatus.INITIALIZING
            self._stop_event.clear()

            if self.bus:
                # 1. Register Manifest with Agent Memory Bus
                self.bus.register_agent(self.get_manifest())
                # 2. Grant Default Workspace ACL Permission Tier
                workspace_pattern = f"workspace/{self.agent_id}/*"
                try:
                    self.bus.grant_permission(workspace_pattern, self.agent_id, AccessTier.OWNER)
                except Exception as err:
                    logger.debug(f"[{self.name}] ACL grant notice: {err}")

            self.status = AgentStatus.ONLINE
            self._is_initialized = True

            # 3. Start Heartbeat Thread
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name=f"AgentHeartbeat-{self.agent_id}",
                daemon=True,
            )
            self._heartbeat_thread.start()
            logger.info(f"[{self.name}] Agent initialized cleanly (ID: '{self.agent_id}').")

    def shutdown(self) -> None:
        """Cleanly stop background heartbeat thread, unregister, and set OFFLINE."""
        with self._lock:
            if not self._is_initialized:
                return
            self._stop_event.set()
            self._is_initialized = False

        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1.0)

        with self._lock:
            if self.bus:
                try:
                    self.bus.unregister_agent(self.agent_id)
                except Exception as err:
                    logger.warning(f"[{self.name}] Error unregistering agent from bus: {err}")

            self.status = AgentStatus.OFFLINE
            logger.info(f"[{self.name}] Agent shutdown cleanly.")

    def health_check(self) -> Dict[str, Any]:
        """Return agent operational health status and telemetry metrics."""
        with self._lock:
            healthy = self.status in [AgentStatus.ONLINE, AgentStatus.BUSY]
            return {
                "status": self.status.value,
                "healthy": healthy,
                "agent_id": self.agent_id,
                "name": self.name,
                "capabilities": list(self.capabilities),
                "active_tasks_count": len(self._active_tasks),
                "metrics": dict(self._metrics),
            }

    def get_metrics(self) -> Dict[str, Any]:
        """Return agent runtime metrics."""
        with self._lock:
            return dict(self._metrics)

    def configure(self, config_data: Dict[str, Any]) -> None:
        """Apply configuration parameters to agent."""
        with self._lock:
            if "heartbeat_interval" in config_data:
                self._heartbeat_interval = float(config_data["heartbeat_interval"])

    def _heartbeat_loop(self) -> None:
        """Background loop sending heartbeats to AgentMemoryBus HealthMonitor."""
        while not self._stop_event.is_set():
            if self.bus:
                try:
                    self.bus.heartbeat(self.agent_id)
                except Exception as err:
                    logger.warning(f"[{self.name}] Heartbeat failed: {err}")
            time.sleep(self._heartbeat_interval)

    # -------------------------------------------------------------------------
    # TASK EXECUTION INTERFACE
    # -------------------------------------------------------------------------
    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Standard legacy entrypoint delegating to execute_task."""
        ctx = context or {}
        task_id = ctx.get("task_id") or f"tsk_{uuid.uuid4().hex[:8]}"
        payload = {"task": task, "context": ctx}
        res = self.execute_task(task_id, payload)
        if res.get("status") == "SUCCESS":
            return str(res.get("result", "Completed successfully."))
        return f"Error: {res.get('error', 'Task execution failed.')}"

    def execute_task(self, task_id: str, payload: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
        """
        Execute domain task with lifecycle telemetry, status management,
        automatic retry with exponential backoff, and scratchpad logging.
        """
        t0 = time.perf_counter()
        with self._lock:
            if self.status == AgentStatus.OFFLINE:
                return {"status": "ERROR", "error": f"Agent '{self.name}' is OFFLINE."}

            self.status = AgentStatus.BUSY
            self._active_tasks[task_id] = {
                "started_at": time.time(),
                "payload": payload,
            }

        self.append_scratchpad(task_id, f"Agent '{self.name}' started task execution.")

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = self._do_execute_task(task_id, payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0

                with self._lock:
                    self._active_tasks.pop(task_id, None)
                    self.status = AgentStatus.ONLINE
                    self._metrics["tasks_executed"] += 1
                    self._metrics["total_execution_time_ms"] += elapsed_ms

                if attempt > 0:
                    logger.info(f"[{self.name}] Task '{task_id}' succeeded on attempt {attempt + 1}")
                self.append_scratchpad(task_id, f"Agent '{self.name}' completed task in {elapsed_ms:.2f} ms.")
                return {
                    "status": "SUCCESS",
                    "task_id": task_id,
                    "agent_id": self.agent_id,
                    "result": result,
                    "elapsed_ms": elapsed_ms,
                    "attempts": attempt + 1,
                }
            except Exception as ex:
                last_error = ex
                elapsed_ms = (time.perf_counter() - t0) * 1000.0

                if attempt < max_retries:
                    backoff = min(2 ** attempt, 4)
                    logger.warning(
                        f"[{self.name}] Task '{task_id}' attempt {attempt + 1} failed: {ex}. "
                        f"Retrying in {backoff}s..."
                    )
                    self.append_scratchpad(task_id, f"Agent '{self.name}' attempt {attempt + 1} failed: {ex}. Retrying.")
                    time.sleep(backoff)
                else:
                    logger.error(f"[{self.name}] Task '{task_id}' failed after {max_retries + 1} attempts: {ex}")

        # All retries exhausted
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        with self._lock:
            self._active_tasks.pop(task_id, None)
            self.status = AgentStatus.DEGRADED
            self._metrics["tasks_failed"] += 1
            if not self._active_tasks:
                self.status = AgentStatus.ONLINE

        self.append_scratchpad(task_id, f"Agent '{self.name}' task failed after {max_retries + 1} attempts: {last_error}")

        return {
            "status": "ERROR",
            "task_id": task_id,
            "agent_id": self.agent_id,
            "error": str(last_error),
            "elapsed_ms": elapsed_ms,
            "attempts": max_retries + 1,
        }

    @abstractmethod
    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        """Abstract domain execution logic to be implemented by concrete agent subclasses."""
        pass

    def cancel_task(self, task_id: str) -> bool:
        """Cancel an active task on this agent."""
        with self._lock:
            if task_id in self._active_tasks:
                self._active_tasks.pop(task_id, None)
                self.append_scratchpad(task_id, f"Agent '{self.name}' cancelled task '{task_id}'.")
                if not self._active_tasks and self.status == AgentStatus.BUSY:
                    self.status = AgentStatus.ONLINE
                return True
            return False

    # -------------------------------------------------------------------------
    # AGENT BUS INTEGRATION HELPERS
    # -------------------------------------------------------------------------
    def send_message(
        self,
        recipient_id: str,
        payload: Dict[str, Any],
        topic: str = "general",
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """Send a message envelope to recipient agent via AgentMemoryBus."""
        if not self.bus:
            logger.warning(f"[{self.name}] Cannot send message: AgentMemoryBus not attached.")
            return ""

        envelope = AgentMessage(
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            topic=topic,
            priority=priority,
            payload=payload,
            agent_ownership=self.agent_id,
        )
        msg_id = self.bus.send_message(envelope)
        with self._lock:
            self._metrics["messages_sent"] += 1
        return msg_id

    def receive_message(self, timeout: float = 0.1) -> Optional[AgentMessage]:
        """Receive top priority message envelope from agent inbox."""
        if not self.bus:
            return None
        envelope = self.bus.receive_message(self.agent_id, timeout=timeout)
        if envelope:
            with self._lock:
                self._metrics["messages_received"] += 1
        return envelope

    def acknowledge_message(self, message_id: str) -> bool:
        """Acknowledge (ACK) successful processing of a message."""
        return self.bus.acknowledge_message(message_id) if self.bus else False

    def negative_acknowledge(self, message_id: str, reason: str = "") -> bool:
        """Negative acknowledge (NACK) message processing with retry or DLQ."""
        return self.bus.negative_acknowledge(message_id, reason=reason) if self.bus else False

    def read_workspace(self, key: str, task_id: Optional[str] = None) -> Optional[Any]:
        """Read a key from WorkspaceStore."""
        return self.bus.read_workspace(key, agent_id=self.agent_id, task_id=task_id) if self.bus else None

    def write_workspace(self, key: str, value: Any, task_id: str = "") -> int:
        """Write a key-value entry to WorkspaceStore."""
        return self.bus.write_workspace(key, value, owner_agent=self.agent_id, task_id=task_id) if self.bus else 0

    def append_scratchpad(self, task_id: str, entry_text: str) -> None:
        """Append a note entry to task Scratchpad."""
        if self.bus:
            try:
                self.bus.append_scratchpad(task_id, self.agent_id, entry_text)
            except Exception as err:
                logger.debug(f"[{self.name}] Scratchpad append notice: {err}")

    def register_artifact(
        self,
        task_id: str,
        file_path: str,
        mime_type: str = "text/plain",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ArtifactMetadata]:
        """Register a disk file artifact with ArtifactRegistry."""
        if self.bus:
            try:
                return self.bus.register_artifact(
                    task_id,
                    file_path,
                    mime_type=mime_type,
                    owner_agent=self.agent_id,
                    metadata=metadata,
                )
            except Exception as err:
                logger.warning(f"[{self.name}] Artifact registration error: {err}")
        return None
