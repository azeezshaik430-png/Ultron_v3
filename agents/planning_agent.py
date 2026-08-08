"""
ULTRON V3 - Planning / Reasoning Agent
Domain Agent responsible for converting high-level user requests into structured plans,
validating step dependencies, selecting target agents, tracking plan execution state,
handling failed steps, and generating final summaries.
"""

import time
import uuid
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional

from core.logger import logger
from agents.base_ultron_agent import BaseUltronAgent


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class PlanStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class PlanStep:
    """Structured representation of an individual execution step within a plan."""
    step_id: str
    description: str
    required_capability: str
    target_agent: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    cancellation_state: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, Enum) else str(self.status)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        d = dict(data)
        if "status" in d and isinstance(d["status"], str):
            d["status"] = StepStatus(d["status"])
        return cls(**d)


@dataclass
class ExecutionPlan:
    """Structured representation of a multi-step execution plan."""
    plan_id: str
    title: str
    description: str
    steps: List[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.CREATED
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    owner_agent: str = "planning_agent"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "owner_agent": self.owner_agent,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPlan":
        steps_data = data.get("steps", [])
        steps = [PlanStep.from_dict(s) if isinstance(s, dict) else s for s in steps_data]
        status = PlanStatus(data["status"]) if isinstance(data.get("status"), str) else data.get("status", PlanStatus.CREATED)
        return cls(
            plan_id=data["plan_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            steps=steps,
            status=status,
            created_at=data.get("created_at", time.time()),
            completed_at=data.get("completed_at"),
            owner_agent=data.get("owner_agent", "planning_agent"),
            metadata=data.get("metadata", {}),
        )


class PlanningAgent(BaseUltronAgent):
    """
    Planning / Reasoning Agent responsible for structured plan generation,
    step dependency validation, agent capability matching, execution progress tracking,
    failed step recovery, and final execution summary production.
    """

    def __init__(
        self,
        agent_id: str = "planning_agent",
        name: str = "Planning Agent",
        description: str = "Agent responsible for request decomposition, plan generation, dependency validation, progress tracking, and failure recovery.",
        capabilities: Optional[List[str]] = None,
        supported_skills: Optional[List[str]] = None,
        bus: Optional[Any] = None,
        version: str = "1.0.0",
    ) -> None:
        default_capabilities = [
            "convert_request_to_plan",
            "create_plan",
            "generate_execution_plan",
            "validate_plan_dependencies",
            "detect_missing_capabilities",
            "estimate_task_state_progress",
            "track_plan_execution_state",
            "handle_failed_step",
            "support_retry_recovery",
            "produce_final_summary",
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

        self._plan_lock = threading.RLock()
        self._plans: Dict[str, ExecutionPlan] = {}

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        """
        Execute domain task commands dispatched by Orchestrator.
        """
        command = payload.get("command") or payload.get("action") or "create_plan"

        if command in ["create_plan", "convert_request_to_plan", "generate_execution_plan"]:
            request = payload.get("request") or payload.get("description") or "Default request"
            steps_spec = payload.get("steps") or payload.get("steps_spec")
            title = payload.get("title", "")
            plan = self.create_plan(request, steps_spec=steps_spec, title=title)
            return plan.to_dict()
        elif command == "validate_plan":
            plan_id = payload.get("plan_id", task_id)
            return self.validate_plan(plan_id)
        elif command == "update_step_status":
            return self.update_step_status(
                payload.get("plan_id", task_id),
                payload.get("step_id", ""),
                payload.get("status", StepStatus.COMPLETED),
                result=payload.get("result"),
                error=payload.get("error"),
            )
        elif command == "handle_failed_step":
            return self.handle_failed_step(
                payload.get("plan_id", task_id),
                payload.get("step_id", ""),
                payload.get("error", "Step execution failed."),
            )
        elif command == "retry_step":
            return self.retry_failed_step(payload.get("plan_id", task_id), payload.get("step_id", ""))
        elif command == "cancel_plan":
            return self.cancel_plan(payload.get("plan_id", task_id))
        elif command == "generate_summary":
            return self.generate_summary(payload.get("plan_id", task_id))
        else:
            # Fallback plan generation
            request = payload.get("request", "Execute request")
            plan = self.create_plan(request)
            return plan.to_dict()

    # -------------------------------------------------------------------------
    # DOMAIN PLANNING CAPABILITIES
    # -------------------------------------------------------------------------

    def create_plan(
        self,
        request: str,
        steps_spec: Optional[List[Dict[str, Any]]] = None,
        title: str = "",
    ) -> ExecutionPlan:
        """
        Decompose high-level request into a structured multi-step ExecutionPlan.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:10]}"
        plan_title = title or f"Plan: {request[:40]}"

        steps: List[PlanStep] = []
        if steps_spec:
            for idx, spec in enumerate(steps_spec):
                s_id = spec.get("step_id") or f"step_{idx + 1}"
                s_desc = spec.get("description") or f"Step {idx + 1}"
                req_cap = spec.get("required_capability") or spec.get("capability") or "general_task"
                target_agent = spec.get("target_agent") or self.select_target_agent(req_cap)
                deps = spec.get("dependencies") or []
                max_retries = int(spec.get("max_retries", 3))

                step = PlanStep(
                    step_id=s_id,
                    description=s_desc,
                    required_capability=req_cap,
                    target_agent=target_agent,
                    dependencies=list(deps),
                    max_retries=max_retries,
                    metadata=spec.get("metadata", {}),
                )
                steps.append(step)
        else:
            # Generate baseline 2-step plan for un-parsed request
            s1 = PlanStep(
                step_id="step_1",
                description=f"Analyze and process initial request: '{request}'",
                required_capability="system_info",
                target_agent=self.select_target_agent("system_info") or "system_agent",
            )
            s2 = PlanStep(
                step_id="step_2",
                description=f"Store and finalize results for: '{request}'",
                required_capability="store_memory",
                target_agent=self.select_target_agent("store_memory") or "memory_agent",
                dependencies=["step_1"],
            )
            steps = [s1, s2]

        plan = ExecutionPlan(
            plan_id=plan_id,
            title=plan_title,
            description=request,
            steps=steps,
            status=PlanStatus.CREATED,
            owner_agent=self.agent_id,
        )

        with self._plan_lock:
            self._plans[plan_id] = plan

        # Persist plan to WorkspaceStore
        ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
        self.write_workspace(ws_key, plan.to_dict(), task_id=plan_id)
        self.append_scratchpad(plan_id, f"Generated plan '{plan_id}' with {len(steps)} steps.")

        return plan

    def validate_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Validate plan structure, step dependencies, cycle detection, and missing capabilities.
        """
        with self._plan_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
                data = self.read_workspace(ws_key, task_id=plan_id)
                if data:
                    plan = ExecutionPlan.from_dict(data)
                    self._plans[plan_id] = plan
                else:
                    raise KeyError(f"Plan '{plan_id}' not found.")

        validation_errors: List[str] = []
        missing_capabilities: List[str] = []
        step_ids = {s.step_id for s in plan.steps}

        # 1. Dependency integrity check
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    validation_errors.append(f"Step '{step.step_id}' references unknown dependency '{dep}'.")

        # 2. Cycle detection (Kahn's algorithm / DFS)
        graph = {s.step_id: set(s.dependencies) for s in plan.steps}
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for s_id in step_ids:
            if s_id not in visited:
                if has_cycle(s_id):
                    validation_errors.append("Cyclic dependency detected among plan steps.")
                    break

        # 3. Capability & Target Agent resolution check
        for step in plan.steps:
            target = step.target_agent or self.select_target_agent(step.required_capability)
            if not target:
                missing_capabilities.append(step.required_capability)
            else:
                step.target_agent = target

        valid = len(validation_errors) == 0
        plan.status = PlanStatus.VALIDATED if valid else PlanStatus.FAILED

        # Update WorkspaceStore
        ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
        self.write_workspace(ws_key, plan.to_dict(), task_id=plan_id)
        self.append_scratchpad(plan_id, f"Validated plan '{plan_id}': valid={valid}, errors={len(validation_errors)}.")

        return {
            "plan_id": plan_id,
            "valid": valid,
            "errors": validation_errors,
            "missing_capabilities": list(set(missing_capabilities)),
            "status": plan.status.value,
        }

    def select_target_agent(self, required_capability: str) -> Optional[str]:
        """
        Find an appropriate agent supporting the required capability from AgentRegistry or defaults.
        """
        if self.bus and hasattr(self.bus, "registry") and self.bus.registry:
            try:
                agents = self.bus.registry.find_agents_by_capability(required_capability)
                if agents:
                    return agents[0].agent_id
            except Exception as err:
                logger.debug(f"[{self.name}] Capability lookup notice: {err}")

        # Fallback known domain agent mappings
        capability_map = {
            "application_control": "system_agent",
            "system_info": "system_agent",
            "file_operations": "system_agent",
            "windows_control": "system_agent",
            "volume_control": "system_agent",
            "app_discovery": "system_agent",
            "store_memory": "memory_agent",
            "retrieve_memory": "memory_agent",
            "update_memory": "memory_agent",
            "delete_memory": "memory_agent",
            "search_knowledge": "memory_agent",
            "create_task": "background_task_agent",
            "start_task": "background_task_agent",
            "generate_execution_plan": "planning_agent",
        }
        return capability_map.get(required_capability)

    def update_step_status(
        self,
        plan_id: str,
        step_id: str,
        status: Any,
        result: Any = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update the execution status of a specific step in a plan and evaluate overall plan progress.
        """
        with self._plan_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
                data = self.read_workspace(ws_key, task_id=plan_id)
                if data:
                    plan = ExecutionPlan.from_dict(data)
                    self._plans[plan_id] = plan
                else:
                    raise KeyError(f"Plan '{plan_id}' not found.")

            target_step: Optional[PlanStep] = None
            for s in plan.steps:
                if s.step_id == step_id:
                    target_step = s
                    break

            if not target_step:
                raise KeyError(f"Step '{step_id}' not found in plan '{plan_id}'.")

            if isinstance(status, str):
                status_enum = StepStatus(status)
            else:
                status_enum = status

            target_step.status = status_enum
            if status_enum == StepStatus.RUNNING and not target_step.started_at:
                target_step.started_at = time.time()
            elif status_enum in [StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.CANCELLED]:
                target_step.completed_at = time.time()

            if result is not None:
                target_step.result = result
            if error is not None:
                target_step.error = error

            # Evaluate overall plan status
            all_completed = all(s.status == StepStatus.COMPLETED for s in plan.steps)
            any_failed = any(s.status == StepStatus.FAILED and s.retry_count >= s.max_retries for s in plan.steps)
            any_cancelled = any(s.status == StepStatus.CANCELLED for s in plan.steps)

            if all_completed:
                plan.status = PlanStatus.COMPLETED
                plan.completed_at = time.time()
            elif any_failed:
                plan.status = PlanStatus.FAILED
            elif any_cancelled:
                plan.status = PlanStatus.CANCELLED
            else:
                plan.status = PlanStatus.IN_PROGRESS

        # Save to WorkspaceStore
        ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
        self.write_workspace(ws_key, plan.to_dict(), task_id=plan_id)
        self.append_scratchpad(plan_id, f"Step '{step_id}' updated to '{status_enum.value}'.")

        return {
            "plan_id": plan_id,
            "step_id": step_id,
            "step_status": target_step.status.value,
            "plan_status": plan.status.value,
        }

    def handle_failed_step(self, plan_id: str, step_id: str, error_message: str) -> Dict[str, Any]:
        """
        Handle a step execution failure, increment retry counter, and evaluate recovery path.
        """
        with self._plan_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                raise KeyError(f"Plan '{plan_id}' not found.")

            target_step = next((s for s in plan.steps if s.step_id == step_id), None)
            if not target_step:
                raise KeyError(f"Step '{step_id}' not found in plan '{plan_id}'.")

            target_step.retry_count += 1
            target_step.error = error_message

            can_retry = target_step.retry_count < target_step.max_retries
            if can_retry:
                target_step.status = StepStatus.PENDING
            else:
                target_step.status = StepStatus.FAILED
                plan.status = PlanStatus.FAILED

        ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
        self.write_workspace(ws_key, plan.to_dict(), task_id=plan_id)
        self.append_scratchpad(plan_id, f"Step '{step_id}' failed: {error_message}. Can retry: {can_retry}")

        return {
            "plan_id": plan_id,
            "step_id": step_id,
            "retry_count": target_step.retry_count,
            "can_retry": can_retry,
            "step_status": target_step.status.value,
            "plan_status": plan.status.value,
        }

    def retry_failed_step(self, plan_id: str, step_id: str) -> bool:
        """Reset a failed step back to PENDING if retries remain."""
        with self._plan_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            step = next((s for s in plan.steps if s.step_id == step_id), None)
            if not step:
                return False
            if step.retry_count < step.max_retries:
                step.status = StepStatus.PENDING
                step.error = None
                plan.status = PlanStatus.IN_PROGRESS
                ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
                self.write_workspace(ws_key, plan.to_dict(), task_id=plan_id)
                self.append_scratchpad(plan_id, f"Retrying step '{step_id}'.")
                return True
            return False

    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel an execution plan and mark pending/running steps CANCELLED."""
        with self._plan_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
                data = self.read_workspace(ws_key, task_id=plan_id)
                if data:
                    plan = ExecutionPlan.from_dict(data)
                    self._plans[plan_id] = plan

            if not plan:
                return False

            plan.status = PlanStatus.CANCELLED
            for step in plan.steps:
                if step.status in [StepStatus.PENDING, StepStatus.RUNNING]:
                    step.status = StepStatus.CANCELLED
                    step.cancellation_state = True

            ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
            self.write_workspace(ws_key, plan.to_dict(), task_id=plan_id)
            self.append_scratchpad(plan_id, f"Plan '{plan_id}' cancelled.")
            return True

    def generate_summary(self, plan_id: str) -> str:
        """Generate human-readable execution summary of plan progress and outcome."""
        with self._plan_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                ws_key = f"workspace/{self.agent_id}/plans/{plan_id}"
                data = self.read_workspace(ws_key, task_id=plan_id)
                if data:
                    plan = ExecutionPlan.from_dict(data)
                else:
                    return f"Error: Plan '{plan_id}' not found."

        total_steps = len(plan.steps)
        completed = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
        pending = sum(1 for s in plan.steps if s.status == StepStatus.PENDING)

        duration_sec = 0.0
        if plan.completed_at:
            duration_sec = plan.completed_at - plan.created_at

        lines = [
            f"# Execution Summary: {plan.title}",
            f"**Plan ID**: {plan.plan_id}",
            f"**Status**: {plan.status.value}",
            f"**Total Steps**: {total_steps} (Completed: {completed}, Failed: {failed}, Pending: {pending})",
            f"**Duration**: {duration_sec:.2f}s",
            "\n### Step Details:",
        ]

        for idx, step in enumerate(plan.steps, 1):
            agent_str = f" [{step.target_agent}]" if step.target_agent else ""
            err_str = f" - Error: {step.error}" if step.error else ""
            lines.append(f"{idx}. `{step.step_id}` ({step.status.value}){agent_str}: {step.description}{err_str}")

        summary_text = "\n".join(lines)
        self.append_scratchpad(plan_id, f"Generated summary for plan '{plan_id}'.")
        return summary_text
