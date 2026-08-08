"""
ULTRON V3 - Coding Domain Agent
Domain Agent responsible for repository inspection, file structure analysis,
code generation, authorized code modification, AST syntax validation,
authorized test execution, test failure inspection, patch artifact generation,
and transaction-backed rollback/recovery.

Integrates with Phase 2A/2B infrastructure:
- BaseUltronAgent / AgentMemoryBus / AgentRegistry
- WorkspaceACL / WorkspaceStore / TransactionManager / Scratchpad / ArtifactRegistry
- RecoveryJournal / MetricsTelemetry
"""

import os
import ast
import time
import uuid
import re
import subprocess
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

from core.logger import logger
from core.exceptions import PermissionDeniedException
from agents.base_ultron_agent import BaseUltronAgent
from brain.bus_types import AgentStatus, ArtifactMetadata
from brain.workspace_acl import AccessTier


class CodingTaskStatus(str, Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    VALIDATED = "VALIDATED"
    TESTED = "TESTED"
    COMPLETED = "COMPLETED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class CodePatch:
    """Structured representation of a code modification patch."""
    patch_id: str
    target_file: str
    original_content: str
    modified_content: str
    diff_summary: str = ""
    syntax_valid: bool = True
    syntax_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodePatch":
        return cls(**data)


@dataclass
class CodingTask:
    """Structured representation of a coding task."""
    task_id: str
    description: str
    target_files: List[str] = field(default_factory=list)
    patches: List[CodePatch] = field(default_factory=list)
    test_results: Dict[str, Any] = field(default_factory=dict)
    status: CodingTaskStatus = CodingTaskStatus.CREATED
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    artifact_id: Optional[str] = None
    owner: str = "coding_agent"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "target_files": list(self.target_files),
            "patches": [p.to_dict() for p in self.patches],
            "test_results": dict(self.test_results),
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "artifact_id": self.artifact_id,
            "owner": self.owner,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodingTask":
        d = dict(data)
        if "patches" in d and isinstance(d["patches"], list):
            d["patches"] = [
                CodePatch.from_dict(p) if isinstance(p, dict) else p
                for p in d["patches"]
            ]
        if "status" in d and isinstance(d["status"], str):
            d["status"] = CodingTaskStatus(d["status"])
        return cls(**d)


class CodingAgent(BaseUltronAgent):
    """
    Coding Domain Agent for ULTRON V3.

    Responsibilities:
    - Repository structure and file content inspection.
    - Code generation and authorized file modification under WorkspaceACL.
    - Python AST syntax validation.
    - Authorized test execution via safe subprocess arrays (shell=False).
    - Test failure analysis and diagnostic reporting.
    - Patch artifact generation with automatic secrets redaction.
    - Transaction-backed backup and rollback of modified files.
    """

    SECRET_PATTERN = re.compile(
        r"(api[_-]?key|secret|password|auth[_-]?token|private[_-]?key)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{8,})['\"]?",
        re.IGNORECASE,
    )

    def __init__(
        self,
        agent_id: str = "coding_agent",
        name: str = "Coding Agent",
        description: str = "Domain Agent for repository inspection, code generation, modification, syntax validation, test execution, patch artifacts, and transaction rollback.",
        bus: Optional[Any] = None,
        version: str = "1.0.0",
    ) -> None:
        capabilities = [
            "inspect_project_files",
            "understand_repo_structure",
            "generate_code",
            "modify_code",
            "validate_syntax",
            "run_authorized_tests",
            "inspect_test_failures",
            "produce_patch_artifact",
            "rollback_code_changes",
            "query_coding_status",
        ]
        supported_skills = [
            "file_manager",
            "search_files",
            "read_text",
            "write_text",
        ]
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=capabilities,
            supported_skills=supported_skills,
            bus=bus,
            version=version,
        )
        self._coding_tasks: Dict[str, CodingTask] = {}
        self._backups: Dict[str, Dict[str, str]] = {}  # task_id -> {file_path: original_content}
        self._task_lock = threading.RLock()

    # =========================================================================
    # DOMAIN TASK EXECUTION IMPLEMENTATION
    # =========================================================================

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        """
        Execute coding domain task actions. Called internally by BaseUltronAgent.execute_task().
        """
        if not isinstance(payload, dict):
            payload = {"action": "generate_code", "description": str(payload)}

        action = payload.get("action") or payload.get("command") or "generate_code"

        if action in ["inspect_project_files", "inspect_files"]:
            return self.inspect_project_files(payload)
        elif action in ["understand_repo_structure", "inspect_repo"]:
            return self.understand_repo_structure(payload)
        elif action in ["generate_code", "create_code"]:
            return self.generate_code(payload)
        elif action in ["modify_code", "write_code"]:
            return self.modify_code(payload)
        elif action in ["validate_syntax", "check_syntax"]:
            return self.validate_syntax(payload)
        elif action in ["run_authorized_tests", "run_tests"]:
            return self.run_authorized_tests(payload)
        elif action in ["inspect_test_failures", "analyze_failures"]:
            return self.inspect_test_failures(payload)
        elif action in ["produce_patch_artifact", "create_patch"]:
            return self.produce_patch_artifact(payload)
        elif action in ["rollback_code_changes", "rollback"]:
            return self.rollback_code_changes(payload)
        elif action in ["query_coding_status", "get_status"]:
            return self.query_coding_status(payload)
        else:
            raise ValueError(f"Unsupported action '{action}' for CodingAgent.")

    # =========================================================================
    # CORE CODING CAPABILITIES
    # =========================================================================

    def inspect_project_files(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Inspect contents of specified project files under WorkspaceACL."""
        file_path = payload.get("file_path") or payload.get("path")
        if not file_path:
            raise ValueError("File inspection requires 'file_path'.")

        self._verify_workspace_acl(file_path, AccessTier.READ)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        clean_content = self._redact_secrets(content)
        line_count = len(clean_content.splitlines())

        return {
            "file_path": file_path,
            "exists": True,
            "size_bytes": len(clean_content.encode("utf-8")),
            "line_count": line_count,
            "content": clean_content,
        }

    def understand_repo_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Traverse directory tree to inspect repository structure under WorkspaceACL."""
        root_path = payload.get("root_path") or os.getcwd()
        max_depth = int(payload.get("max_depth", 3))

        self._verify_workspace_acl(root_path, AccessTier.READ)

        tree: List[Dict[str, Any]] = []

        def _scan(curr_path: str, depth: int):
            if depth > max_depth:
                return
            try:
                for entry in os.scandir(curr_path):
                    if entry.name.startswith(".") or entry.name in ["__pycache__", "node_modules", "venv", "ultron_env"]:
                        continue
                    rel_p = os.path.relpath(entry.path, root_path)
                    if entry.is_dir():
                        tree.append({"path": rel_p, "type": "directory", "depth": depth})
                        _scan(entry.path, depth + 1)
                    else:
                        tree.append({"path": rel_p, "type": "file", "depth": depth, "size": entry.stat().st_size})
            except PermissionError:
                pass

        _scan(root_path, 1)

        return {
            "root_path": root_path,
            "total_items": len(tree),
            "structure": tree[:200],
        }

    def generate_code(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code snippet or template based on payload specifications."""
        language = payload.get("language", "python").lower()
        spec = payload.get("specification", payload.get("description", ""))

        if language == "python":
            code = f'"""\nGenerated Python module for: {spec}\n"""\n\n'
            code += "def main():\n    print('ULTRON V3 Generated Execution')\n\n"
            code += "if __name__ == '__main__':\n    main()\n"
        else:
            code = f"// Generated {language} code for: {spec}\n"

        # Validate syntax if python
        valid, err = self._validate_python_ast(code) if language == "python" else (True, None)

        return {
            "language": language,
            "specification": spec,
            "code": code,
            "syntax_valid": valid,
            "syntax_error": err,
        }

    def modify_code(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modify target file content with WorkspaceACL check and transaction backup.
        """
        target_file = payload.get("target_file") or payload.get("path")
        new_content = payload.get("content")
        c_id = payload.get("coding_id", f"code_{uuid.uuid4().hex[:8]}")

        if not target_file or new_content is None:
            raise ValueError("Code modification requires 'target_file' and 'content'.")

        self._verify_workspace_acl(target_file, AccessTier.WRITE)

        # Step 1: Backup original content for transaction rollback
        original_content = ""
        if os.path.exists(target_file):
            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                original_content = f.read()

        with self._task_lock:
            if c_id not in self._backups:
                self._backups[c_id] = {}
            self._backups[c_id][target_file] = original_content

        # Step 2: Validate AST syntax if python
        is_python = target_file.endswith(".py")
        valid, err = self._validate_python_ast(new_content) if is_python else (True, None)

        if not valid and payload.get("strict_syntax", True):
            return {
                "status": "SYNTAX_ERROR",
                "target_file": target_file,
                "syntax_valid": False,
                "syntax_error": err,
                "message": f"Syntax validation failed for '{target_file}': {err}",
            }

        # Step 3: Write new content
        os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Step 4: Record patch object
        diff_summary = f"Modified {target_file}: {len(original_content)} -> {len(new_content)} bytes"
        patch = CodePatch(
            patch_id=f"patch_{uuid.uuid4().hex[:6]}",
            target_file=target_file,
            original_content=original_content,
            modified_content=new_content,
            diff_summary=diff_summary,
            syntax_valid=valid,
            syntax_error=err,
        )

        with self._task_lock:
            if c_id not in self._coding_tasks:
                self._coding_tasks[c_id] = CodingTask(task_id=c_id, description=f"Modify {target_file}")
            task = self._coding_tasks[c_id]
            task.target_files.append(target_file)
            task.patches.append(patch)
            task.status = CodingTaskStatus.VALIDATED if valid else CodingTaskStatus.IN_PROGRESS

        return {
            "coding_id": c_id,
            "target_file": target_file,
            "modified": True,
            "syntax_valid": valid,
            "syntax_error": err,
            "bytes_written": len(new_content.encode("utf-8")),
        }

    def validate_syntax(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate code syntax without writing to disk."""
        code = payload.get("code")
        file_path = payload.get("file_path")

        if file_path and not code:
            self._verify_workspace_acl(file_path, AccessTier.READ)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    code = f.read()

        if code is None:
            raise ValueError("Syntax validation requires 'code' or 'file_path'.")

        valid, err = self._validate_python_ast(code)
        return {
            "syntax_valid": valid,
            "syntax_error": err,
            "code_length": len(code),
        }

    def run_authorized_tests(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute authorized unit tests using safe subprocess array (shell=False).
        SECURITY: Unrestricted shell strings are prohibited.
        """
        test_target = payload.get("test_target") or payload.get("target")
        test_runner = payload.get("runner", "pytest")

        if not test_target:
            raise ValueError("Test execution requires 'test_target'.")

        # ACL permission check for test target path
        if os.path.exists(test_target):
            self._verify_workspace_acl(test_target, AccessTier.READ)

        # Build safe subprocess command array (NEVER shell=True)
        if test_runner == "pytest":
            cmd = [os.sys.executable, "-m", "pytest", test_target, "-v", "--tb=short"]
        elif test_runner == "unittest":
            cmd = [os.sys.executable, "-m", "unittest", test_target]
        else:
            cmd = [os.sys.executable, test_target]

        start_t = time.time()
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=float(payload.get("timeout_sec", 60.0)),
            )
            elapsed_sec = time.time() - start_t
            success = (result.returncode == 0)

            out_clean = self._redact_secrets(result.stdout)
            err_clean = self._redact_secrets(result.stderr)

            test_res = {
                "runner": test_runner,
                "target": test_target,
                "success": success,
                "exit_code": result.returncode,
                "elapsed_sec": round(elapsed_sec, 2),
                "stdout": out_clean[-2000:],
                "stderr": err_clean[-2000:],
            }

            return test_res

        except subprocess.TimeoutExpired:
            return {
                "runner": test_runner,
                "target": test_target,
                "success": False,
                "exit_code": -1,
                "error": "Test execution timed out.",
            }
        except Exception as exc:
            return {
                "runner": test_runner,
                "target": test_target,
                "success": False,
                "exit_code": -1,
                "error": str(exc),
            }

    def inspect_test_failures(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test failure logs to identify root cause and failing assertions."""
        stdout = payload.get("stdout", "")
        stderr = payload.get("stderr", "")
        logs = f"{stdout}\n{stderr}"

        failures: List[str] = []
        for line in logs.splitlines():
            if "FAILED" in line or "AssertionError" in line or "SyntaxError" in line or "E   " in line:
                failures.append(line.strip())

        return {
            "failure_count": len(failures),
            "summary": f"Identified {len(failures)} diagnostic failure lines." if failures else "No failure patterns detected.",
            "diagnostic_lines": failures[:20],
        }

    def produce_patch_artifact(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a patch artifact and register it with ArtifactRegistry."""
        c_id = payload.get("coding_id")
        title = payload.get("title", "Code Change Patch")
        target_file = payload.get("target_file", "modified_file.py")
        diff_text = payload.get("diff", "")

        with self._task_lock:
            if c_id in self._coding_tasks and not diff_text:
                task = self._coding_tasks[c_id]
                diffs = [f"--- {p.target_file}\n+++ {p.target_file}\n{p.diff_summary}" for p in task.patches]
                diff_text = "\n\n".join(diffs)

        diff_clean = self._redact_secrets(diff_text or "No diff provided.")
        art_id = f"art_patch_{uuid.uuid4().hex[:8]}"

        content = f"# Patch Artifact: {title}\n"
        content += f"**File**: {target_file}\n"
        content += f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += "```diff\n"
        content += f"{diff_clean}\n"
        content += "```\n"

        if self.bus and hasattr(self.bus, "register_artifact"):
            try:
                meta = ArtifactMetadata(
                    artifact_id=art_id,
                    name=f"{title}.patch",
                    artifact_type="diff",
                    creator_id=self.agent_id,
                    content_hash=str(hash(content)),
                    size_bytes=len(content.encode("utf-8")),
                )
                self.bus.register_artifact(meta, content.encode("utf-8"))
            except Exception as err:
                logger.debug(f"[{self.name}] Artifact registration notice: {err}")

        return {
            "artifact_id": art_id,
            "title": title,
            "target_file": target_file,
            "patch_content": content,
        }

    def rollback_code_changes(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Restore original file contents from backup dictionary or TransactionManager.
        """
        c_id = payload.get("coding_id")
        target_file = payload.get("target_file")

        restored_files: List[str] = []

        with self._task_lock:
            if c_id in self._backups:
                backups = self._backups[c_id]
                for path, original in backups.items():
                    if target_file and path != target_file:
                        continue
                    try:
                        self._verify_workspace_acl(path, AccessTier.WRITE)
                        if original:
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(original)
                        elif os.path.exists(path):
                            os.remove(path)
                        restored_files.append(path)
                    except Exception as err:
                        logger.error(f"[{self.name}] Failed to rollback '{path}': {err}")

                if c_id in self._coding_tasks:
                    self._coding_tasks[c_id].status = CodingTaskStatus.ROLLED_BACK

        return {
            "coding_id": c_id,
            "rolled_back": len(restored_files) > 0,
            "restored_files": restored_files,
        }

    def query_coding_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Query coding task execution status."""
        c_id = payload.get("coding_id")
        with self._task_lock:
            if c_id and c_id in self._coding_tasks:
                return {"coding_id": c_id, "task": self._coding_tasks[c_id].to_dict()}
            return {
                "total_tasks": len(self._coding_tasks),
                "tasks": [t.to_dict() for t in self._coding_tasks.values()],
            }

    # =========================================================================
    # PRIVATE UTILITIES
    # =========================================================================

    def _verify_workspace_acl(self, path: str, tier: AccessTier) -> None:
        """Enforce WorkspaceACL checks if bus and ACL manager are available."""
        if self.bus and hasattr(self.bus, "check_permission"):
            try:
                allowed = self.bus.check_permission(path, self.agent_id, tier)
                if not allowed:
                    raise PermissionDeniedException(
                        f"WorkspaceACL blocked '{tier.value}' access for '{self.agent_id}' on path '{path}'"
                    )
            except Exception as err:
                if "PermissionDeniedException" in type(err).__name__:
                    raise err

    @staticmethod
    def _validate_python_ast(code: str) -> Tuple[bool, Optional[str]]:
        """Validate Python code string syntax using ast.parse."""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as err:
            return False, f"SyntaxError at line {err.lineno}: {err.msg}"
        except Exception as exc:
            return False, str(exc)

    def _redact_secrets(self, text: str) -> str:
        """Redact API keys, tokens, and passwords from logs and artifacts."""
        if not text:
            return ""
        return self.SECRET_PATTERN.sub(r"\1=[REDACTED]", text)
