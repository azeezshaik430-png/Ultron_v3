"""
ULTRON V3 - Background Task Agent
Domain Agent for background task creation, scheduling, execution, status tracking,
progress reporting, failure recovery, and artifact management.
"""

import time
import uuid
import threading
from typing import Dict, Any, List, Optional, Callable

from core.logger import logger
from core.task_engine import TaskEngine
from core.task_models import TaskDescriptor, TaskStatus, PriorityLevel
from agents.base_ultron_agent import BaseUltronAgent
from brain.bus_types import AgentStatus


class BackgroundTaskAgent(BaseUltronAgent):
    """
    Background Task Agent responsible for multi-queue task execution,
    lifecycle management, lease/progress tracking, recovery, and artifact handling.
    """

    DESTRUCTIVE_ACTIONS = {
        "shutdown_pc",
        "delete_file",
        "restart_pc",
        "force_kill",
        "wipe_database",
        "execute_shell",
    }

    def __init__(
        self,
        agent_id: str = "background_task_agent",
        name: str = "Background Task Agent",
        description: str = "Agent responsible for background task creation, scheduling, execution, status tracking, retry recovery, and artifact management.",
        capabilities: Optional[List[str]] = None,
        supported_skills: Optional[List[str]] = None,
        bus: Optional[Any] = None,
        version: str = "1.0.0",
        worker_count: int = 2,
    ) -> None:
        default_capabilities = [
            "create_task",
            "start_task",
            "pause_task",
            "resume_task",
            "cancel_task",
            "query_task_status",
            "list_active_tasks",
            "update_progress",
            "retry_task",
            "task_management",
            "artifact_management",
        ]
        caps = capabilities or default_capabilities

        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=caps,
            supported_skills=supported_skills or [],
            bus=bus,
            version=version,
        )

        self._task_lock = threading.RLock()
        self.task_engine = TaskEngine(worker_count=worker_count)
        self._managed_tasks: Dict[str, Dict[str, Any]] = {}

    def initialize(self) -> None:
        """Initialize agent, start internal TaskEngine, and register with memory bus."""
        with self._lock:
            if self._is_initialized:
                return
            super().initialize()
            self.task_engine.start()
            logger.info(f"[{self.name}] Internal TaskEngine started successfully.")

    def shutdown(self) -> None:
        """Shutdown internal TaskEngine and unregister agent."""
        with self._lock:
            if not self._is_initialized:
                return
            self.task_engine.shutdown()
            super().shutdown()
            logger.info(f"[{self.name}] Internal TaskEngine cleanly shutdown.")

    def health_check(self) -> Dict[str, Any]:
        """Return operational health status including task engine metrics."""
        health = super().health_check()
        with self._task_lock:
            health["managed_tasks_count"] = len(self._managed_tasks)
            health["engine_active_tasks"] = self.task_engine.metrics.active_tasks
            health["engine_completed_tasks"] = self.task_engine.metrics.total_completed
            health["engine_failed_tasks"] = self.task_engine.metrics.total_failed
        return health

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        """
        Execute task operations dispatched by Orchestrator or direct invocation.
        """
        command = payload.get("command") or payload.get("action") or "create_task"

        if command in ["create_task", "create_background_task"]:
            return self.create_task(payload)
        elif command == "start_task":
            t_id = payload.get("task_id", task_id)
            return self.start_task(t_id, payload.get("exec_func"))
        elif command == "pause_task":
            return self.pause_task(payload.get("task_id", task_id))
        elif command == "resume_task":
            return self.resume_task(payload.get("task_id", task_id))
        elif command == "cancel_task":
            return self.cancel_task(payload.get("task_id", task_id))
        elif command in ["query_task_status", "get_task_status"]:
            return self.get_task_status(payload.get("target_task_id") or payload.get("task_id", task_id))
        elif command in ["list_active_tasks", "list_tasks"]:
            return self.list_active_tasks()
        elif command == "update_progress":
            return self.update_progress(
                payload.get("target_task_id") or task_id,
                float(payload.get("progress", 0.0)),
                str(payload.get("message", "")),
            )
        elif command == "retry_task":
            return self.retry_task(payload.get("target_task_id") or task_id)
        elif command == "handle_artifact":
            return self.handle_artifact(
                payload.get("target_task_id") or task_id,
                payload.get("file_path", ""),
                payload.get("mime_type", "text/plain"),
                payload.get("metadata"),
            )
        else:
            # Generic background execution wrapper
            return self.create_and_run(task_id, payload)

    # -------------------------------------------------------------------------
    # DOMAIN TASK MANAGEMENT CAPABILITIES
    # -------------------------------------------------------------------------

    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new background task descriptor with security authorization checks.
        """
        action = payload.get("action", "generic_background_job")
        is_privileged = payload.get("privileged", False) or action in self.DESTRUCTIVE_ACTIONS

        if is_privileged:
            confirmed = payload.get("confirmed", False)
            auth_token = payload.get("auth_token")
            if not confirmed and not auth_token:
                logger.warning(f"[{self.name}] Denied unauthorized privileged action '{action}'.")
                raise PermissionError(f"Action '{action}' requires explicit authorization or confirmation.")

        t_id = payload.get("task_id") or f"bg_tsk_{uuid.uuid4().hex[:10]}"
        description = payload.get("description") or f"Background task: {action}"
        priority_val = payload.get("priority", PriorityLevel.NORMAL)

        try:
            priority = PriorityLevel(priority_val)
        except Exception:
            priority = PriorityLevel.NORMAL

        task_record = {
            "task_id": t_id,
            "description": description,
            "action": action,
            "status": TaskStatus.CREATED.value,
            "priority": priority.value,
            "progress": 0.0,
            "owner": payload.get("owner", self.agent_id),
            "created_at": time.time(),
            "started_at": None,
            "completed_at": None,
            "retry_count": 0,
            "max_retries": int(payload.get("max_retries", 3)),
            "result": None,
            "error": None,
            "artifacts": [],
            "metadata": payload.get("metadata", {}),
        }

        with self._task_lock:
            self._managed_tasks[t_id] = task_record

        # Persist task state to WorkspaceStore
        ws_key = f"workspace/{self.agent_id}/tasks/{t_id}"
        self.write_workspace(ws_key, task_record, task_id=t_id)
        self.append_scratchpad(t_id, f"Created task '{t_id}' ({description}).")

        return {"task_id": t_id, "status": TaskStatus.CREATED.value, "task": task_record}

    def start_task(self, task_id: str, exec_func: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Enqueues and starts a created background task in the TaskEngine.
        """
        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)
            if not task_record:
                # Try reading from WorkspaceStore
                ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
                task_record = self.read_workspace(ws_key, task_id=task_id)
                if not task_record:
                    raise KeyError(f"Task '{task_id}' not found.")
                self._managed_tasks[task_id] = task_record

            task_record["status"] = TaskStatus.RUNNING.value
            task_record["started_at"] = time.time()

        ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
        self.write_workspace(ws_key, task_record, task_id=task_id)
        self.append_scratchpad(task_id, f"Task '{task_id}' started execution.")

        # Create TaskDescriptor for PriorityTaskEngine
        descriptor = TaskDescriptor(
            task_id=task_id,
            priority=PriorityLevel(task_record["priority"]),
            status=TaskStatus.VALIDATED,
            owner=self.agent_id,
            max_retries=task_record["max_retries"],
            retry_count=task_record.get("retry_count", 0),
            action=task_record["action"],
            exec_func=exec_func or (lambda: self._default_task_execution(task_id)),
        )

        success = self.task_engine.enqueue(descriptor)
        if not success:
            task_record["status"] = TaskStatus.FAILED.value
            task_record["error"] = "Failed to enqueue task into TaskEngine queue."
            self.write_workspace(ws_key, task_record, task_id=task_id)
            return {"task_id": task_id, "status": TaskStatus.FAILED.value, "error": task_record["error"]}

        return {"task_id": task_id, "status": TaskStatus.RUNNING.value}

    def pause_task(self, task_id: str) -> Dict[str, Any]:
        """Pause queue execution or update task status to WAITING."""
        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)
            if task_record:
                task_record["status"] = TaskStatus.WAITING.value
                ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
                self.write_workspace(ws_key, task_record, task_id=task_id)

        self.task_engine.pause()
        self.append_scratchpad(task_id, "Background task engine paused.")
        return {"status": "PAUSED", "task_id": task_id}

    def resume_task(self, task_id: str) -> Dict[str, Any]:
        """Resume task engine processing."""
        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)
            if task_record:
                task_record["status"] = TaskStatus.RUNNING.value
                ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
                self.write_workspace(ws_key, task_record, task_id=task_id)

        self.task_engine.resume()
        self.append_scratchpad(task_id, "Background task engine resumed.")
        return {"status": "RUNNING", "task_id": task_id}

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or active background task."""
        cancelled_engine = self.task_engine.cancel_task(task_id)
        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)
            if task_record:
                task_record["status"] = TaskStatus.CANCELLED.value
                task_record["completed_at"] = time.time()
                ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
                self.write_workspace(ws_key, task_record, task_id=task_id)
                self.append_scratchpad(task_id, f"Task '{task_id}' was cancelled.")
                return True

        # Also delegate base agent cancel_task
        base_cancelled = super().cancel_task(task_id)
        return cancelled_engine or base_cancelled

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Retrieve task details and current status."""
        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)

        if not task_record:
            ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
            task_record = self.read_workspace(ws_key, task_id=task_id)

        if not task_record:
            # Check engine descriptors
            desc = self.task_engine.get_task(task_id)
            if desc:
                return {
                    "task_id": desc.task_id,
                    "status": desc.status.value,
                    "retry_count": desc.retry_count,
                    "max_retries": desc.max_retries,
                }
            raise KeyError(f"Task '{task_id}' not found.")

        # Sync engine status if available
        desc = self.task_engine.get_task(task_id)
        if desc:
            task_record["status"] = desc.status.value
            task_record["retry_count"] = desc.retry_count

        return task_record

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """Return a list of all active (CREATED, QUEUED, RUNNING, WAITING) tasks."""
        with self._task_lock:
            active = []
            for t_id, record in self._managed_tasks.items():
                if record.get("status") in [
                    TaskStatus.CREATED.value,
                    TaskStatus.QUEUED.value,
                    TaskStatus.RUNNING.value,
                    TaskStatus.WAITING.value,
                ]:
                    active.append(dict(record))
            return active

    def update_progress(self, task_id: str, progress: float, message: str = "") -> Dict[str, Any]:
        """Update progress percentage and message for a task."""
        progress_val = max(0.0, min(100.0, progress))
        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)
            if task_record:
                task_record["progress"] = progress_val
                if message:
                    task_record["metadata"]["last_progress_message"] = message
                ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
                self.write_workspace(ws_key, task_record, task_id=task_id)

        self.append_scratchpad(task_id, f"Progress updated to {progress_val:.1f}% ({message})")
        return {"task_id": task_id, "progress": progress_val, "message": message}

    def retry_task(self, task_id: str) -> Dict[str, Any]:
        """Manually retry a failed background task."""
        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)
            if not task_record:
                raise KeyError(f"Task '{task_id}' not found.")

            if task_record["retry_count"] >= task_record["max_retries"]:
                return {
                    "task_id": task_id,
                    "status": TaskStatus.DLQ.value,
                    "error": "Max retries exceeded; task sent to DLQ.",
                }

            task_record["retry_count"] += 1
            task_record["status"] = TaskStatus.QUEUED.value
            ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
            self.write_workspace(ws_key, task_record, task_id=task_id)

        self.append_scratchpad(task_id, f"Task '{task_id}' manually retried (Attempt {task_record['retry_count']}).")
        return self.start_task(task_id)

    def handle_artifact(
        self,
        task_id: str,
        file_path: str,
        mime_type: str = "text/plain",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a generated artifact file with ArtifactRegistry and attach metadata to task."""
        artifact_meta = self.register_artifact(task_id, file_path, mime_type=mime_type, metadata=metadata)
        artifact_info = {
            "artifact_id": artifact_meta.artifact_id if artifact_meta else f"art_{uuid.uuid4().hex[:8]}",
            "file_path": file_path,
            "mime_type": mime_type,
            "created_at": time.time(),
        }

        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)
            if task_record:
                task_record["artifacts"].append(artifact_info)
                ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
                self.write_workspace(ws_key, task_record, task_id=task_id)

        self.append_scratchpad(task_id, f"Registered artifact '{file_path}' for task '{task_id}'.")
        return {"status": "SUCCESS", "task_id": task_id, "artifact": artifact_info}

    def create_and_run(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Shortcut method to create and start task synchronously or asynchronously."""
        create_res = self.create_task(payload)
        t_id = create_res["task_id"]
        start_res = self.start_task(t_id, payload.get("exec_func"))
        return {"task_id": t_id, "create_status": create_res["status"], "start_status": start_res["status"]}

    # -------------------------------------------------------------------------
    # PRIVATE TASK EXECUTION HELPERS
    # -------------------------------------------------------------------------

    def _default_task_execution(self, task_id: str) -> None:
        """Default execution procedure for background tasks."""
        with self._task_lock:
            task_record = self._managed_tasks.get(task_id)
            if not task_record:
                return
            task_record["status"] = TaskStatus.RUNNING.value
            task_record["progress"] = 50.0

        time.sleep(0.05)  # Simulate execution

        with self._task_lock:
            task_record["status"] = TaskStatus.COMPLETED.value
            task_record["progress"] = 100.0
            task_record["completed_at"] = time.time()
            task_record["result"] = "Task completed successfully."
            ws_key = f"workspace/{self.agent_id}/tasks/{task_id}"
            self.write_workspace(ws_key, task_record, task_id=task_id)
