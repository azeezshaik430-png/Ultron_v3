"""
ULTRON V3 - Research Domain Agent
Domain Agent responsible for information retrieval, source collection,
source validation, findings synthesis, and research artifact generation.

Integrates with Phase 2A/2B infrastructure:
- BaseUltronAgent / AgentMemoryBus / AgentRegistry
- WorkspaceACL / WorkspaceStore / Scratchpad / ArtifactRegistry
- RecoveryJournal / MetricsTelemetry
"""

import os
import time
import uuid
import re
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional

from core.logger import logger
from agents.base_ultron_agent import BaseUltronAgent
from brain.bus_types import AgentStatus, ArtifactMetadata
from brain.workspace_acl import AccessTier


class ResearchTaskStatus(str, Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ResearchSource:
    """Structured representation of an information source."""
    source_id: str = ""
    url_or_path: str = ""
    title: str = ""
    snippet: str = ""
    reliability_score: float = 1.0
    domain: str = ""
    timestamp: float = field(default_factory=time.time)
    is_valid: bool = True
    validation_notes: str = "Valid"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchSource":
        d = dict(data)
        if not d.get("source_id"):
            d["source_id"] = f"src_{uuid.uuid4().hex[:6]}"
        return cls(**d)


@dataclass
class ResearchTask:
    """Structured representation of a research task."""
    task_id: str
    query: str
    topic: str = "general"
    sources: List[ResearchSource] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    summary: str = ""
    status: ResearchTaskStatus = ResearchTaskStatus.CREATED
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    artifact_id: Optional[str] = None
    owner: str = "research_agent"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "query": self.query,
            "topic": self.topic,
            "sources": [s.to_dict() for s in self.sources],
            "findings": list(self.findings),
            "summary": self.summary,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "artifact_id": self.artifact_id,
            "owner": self.owner,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchTask":
        d = dict(data)
        if "sources" in d and isinstance(d["sources"], list):
            d["sources"] = [
                ResearchSource.from_dict(s) if isinstance(s, dict) else s
                for s in d["sources"]
            ]
        if "status" in d and isinstance(d["status"], str):
            d["status"] = ResearchTaskStatus(d["status"])
        return cls(**d)


class ResearchAgent(BaseUltronAgent):
    """
    Research Domain Agent for ULTRON V3.

    Responsibilities:
    - Information retrieval across local files, documents, and configured external providers.
    - Source collection and domain validation.
    - Result synthesis and structured report generation.
    - Registration of research reports with ArtifactRegistry.
    - WorkspaceACL enforcement for file-based research sources.
    - Honest capability availability reporting when external research providers are unconfigured.
    """

    FORBIDDEN_DOMAINS = {"malware.example", "phishing.example", "untrusted.invalid"}

    def __init__(
        self,
        agent_id: str = "research_agent",
        name: str = "Research Agent",
        description: str = "Domain Agent for information retrieval, source validation, synthesis, and artifact generation.",
        bus: Optional[Any] = None,
        version: str = "1.0.0",
    ) -> None:
        capabilities = [
            "create_research_task",
            "conduct_research",
            "information_retrieval",
            "source_collection",
            "source_validation",
            "result_synthesis",
            "generate_research_artifact",
            "cancel_research",
            "query_research_status",
        ]
        supported_skills = [
            "search_files",
            "file_manager",
            "read_text",
            "web_search",
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
        self._research_tasks: Dict[str, ResearchTask] = {}
        self._task_lock = threading.RLock()

    # =========================================================================
    # DOMAIN TASK EXECUTION IMPLEMENTATION
    # =========================================================================

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        """
        Execute research domain task actions. Called internally by BaseUltronAgent.execute_task().
        """
        if not isinstance(payload, dict):
            payload = {"action": "conduct_research", "query": str(payload)}

        action = payload.get("action") or payload.get("command") or "conduct_research"

        if action in ["create_research_task", "create_task"]:
            return self.create_research_task(payload)
        elif action in ["conduct_research", "research"]:
            return self.conduct_research(payload)
        elif action in ["information_retrieval", "search"]:
            return self.retrieve_information(payload)
        elif action in ["source_collection", "collect_sources"]:
            return self.collect_sources(payload)
        elif action in ["source_validation", "validate_sources"]:
            return self.validate_sources(payload)
        elif action in ["result_synthesis", "synthesize"]:
            return self.synthesize_results(payload)
        elif action in ["generate_research_artifact", "create_artifact"]:
            return self.generate_research_artifact(payload)
        elif action in ["cancel_research", "cancel_task"]:
            return self.cancel_research(payload)
        elif action in ["query_research_status", "get_status"]:
            return self.query_research_status(payload)
        else:
            raise ValueError(f"Unsupported action '{action}' for ResearchAgent.")

    # =========================================================================
    # CORE RESEARCH CAPABILITIES
    # =========================================================================

    def create_research_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create and store a new research task descriptor."""
        query = payload.get("query", "").strip()
        if not query:
            raise ValueError("Research task creation requires a non-empty 'query'.")

        topic = payload.get("topic", "general")
        r_id = payload.get("research_id", f"res_{uuid.uuid4().hex[:8]}")

        task = ResearchTask(
            task_id=r_id,
            query=query,
            topic=topic,
            metadata=payload.get("metadata", {}),
        )

        with self._task_lock:
            self._research_tasks[r_id] = task

        # Persist task state in WorkspaceStore if bus available
        if self.bus and hasattr(self.bus, "write_workspace"):
            try:
                path = f"workspace/{self.agent_id}/tasks/{r_id}"
                self.bus.write_workspace(path, task.to_dict(), owner_agent=self.agent_id)
            except Exception as err:
                logger.debug(f"[{self.name}] WorkspaceStore persist notice: {err}")

        return {"research_id": r_id, "task": task.to_dict()}

    def retrieve_information(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Information retrieval capability.
        Supports file-based retrieval, web search, and optional external providers.
        """
        query = payload.get("query", "").lower()
        search_path = payload.get("search_path")
        provider = payload.get("provider")
        search_web = payload.get("search_web", False)

        # Handle explicit missing provider request honestly
        if provider == "unconfigured_web_provider" or payload.get("require_external_api"):
            return {
                "available": False,
                "reason": f"External search provider '{provider or 'web_api'}' is not configured or missing API credentials.",
                "sources": [],
            }

        # Web search via DuckDuckGo
        if search_web or provider in ("web", "duckduckgo", "internet"):
            try:
                from skills.web_search import search_web as ddg_search
                web_result = ddg_search(payload.get("query", query), max_results=payload.get("max_results", 5))
                if web_result.get("status") == "SUCCESS":
                    sources = []
                    for r in web_result.get("results", []):
                        sources.append({
                            "source_id": f"web_{uuid.uuid4().hex[:6]}",
                            "url_or_path": r.get("url", ""),
                            "title": r.get("title", ""),
                            "snippet": r.get("snippet", ""),
                            "reliability_score": 0.7,
                            "domain": "web_search",
                        })
                    answer = web_result.get("answer")
                    if answer:
                        sources.insert(0, {
                            "source_id": f"web_answer_{uuid.uuid4().hex[:6]}",
                            "url_or_path": "duckduckgo_instant",
                            "title": "Instant Answer",
                            "snippet": answer,
                            "reliability_score": 0.9,
                            "domain": "duckduckgo",
                        })
                    return {
                        "available": True,
                        "query": query,
                        "sources_count": len(sources),
                        "sources": sources,
                        "provider": "duckduckgo",
                    }
                else:
                    return {
                        "available": False,
                        "reason": web_result.get("error", "Web search failed"),
                        "sources": [],
                    }
            except Exception as e:
                logger.warning(f"[{self.name}] Web search error: {e}")
                return {
                    "available": False,
                    "reason": f"Web search error: {e}",
                    "sources": [],
                }

        # ACL check for file-based search
        if search_path:
            self._verify_workspace_acl(search_path, AccessTier.READ_ONLY)

        sources: List[ResearchSource] = []

        # Local directory / file scan if search_path specified
        if search_path and os.path.exists(search_path):
            if os.path.isfile(search_path):
                try:
                    with open(search_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if query in content.lower():
                        sources.append(
                            ResearchSource(
                                source_id=f"src_{uuid.uuid4().hex[:6]}",
                                url_or_path=search_path,
                                title=os.path.basename(search_path),
                                snippet=content[:200],
                                reliability_score=1.0,
                                domain="local_file",
                            )
                        )
                except Exception as err:
                    logger.warning(f"[{self.name}] Error reading file '{search_path}': {err}")
            elif os.path.isdir(search_path):
                for root, _, files in os.walk(search_path):
                    for file in files:
                        full_p = os.path.join(root, file)
                        try:
                            with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            if query in content.lower():
                                sources.append(
                                    ResearchSource(
                                        source_id=f"src_{uuid.uuid4().hex[:6]}",
                                        url_or_path=full_p,
                                        title=file,
                                        snippet=content[:200],
                                        reliability_score=0.9,
                                        domain="local_dir",
                                    )
                                )
                        except Exception:
                            continue

        # Provided raw sources in payload
        raw_sources = payload.get("raw_sources", [])
        for s in raw_sources:
            if isinstance(s, dict):
                src_obj = ResearchSource(
                    source_id=s.get("source_id", f"src_{uuid.uuid4().hex[:6]}"),
                    url_or_path=s.get("url_or_path", s.get("url", "unknown")),
                    title=s.get("title", "Untitled Source"),
                    snippet=s.get("snippet", ""),
                    reliability_score=float(s.get("reliability_score", 0.8)),
                    domain=s.get("domain", ""),
                )
                sources.append(src_obj)

        return {
            "available": True,
            "query": query,
            "sources_count": len(sources),
            "sources": [s.to_dict() for s in sources],
        }

    def collect_sources(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Collect and attach sources to a research task."""
        r_id = payload.get("research_id")
        raw_sources = payload.get("sources", [])

        collected: List[ResearchSource] = []
        for s in raw_sources:
            if isinstance(s, dict):
                src = ResearchSource(
                    source_id=s.get("source_id", f"src_{uuid.uuid4().hex[:6]}"),
                    url_or_path=s.get("url_or_path", s.get("url", "")),
                    title=s.get("title", "Untitled Source"),
                    snippet=s.get("snippet", ""),
                    reliability_score=float(s.get("reliability_score", 1.0)),
                    domain=s.get("domain", self._extract_domain(s.get("url_or_path", ""))),
                )
                collected.append(src)
            elif isinstance(s, ResearchSource):
                collected.append(s)

        with self._task_lock:
            if r_id in self._research_tasks:
                task = self._research_tasks[r_id]
                task.sources.extend(collected)
                return {"research_id": r_id, "total_sources": len(task.sources)}

        return {"collected_count": len(collected), "sources": [s.to_dict() for s in collected]}

    def validate_sources(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate collected sources for reliability, security boundaries,
        and content integrity.
        """
        raw_sources = payload.get("sources", [])
        validated: List[Dict[str, Any]] = []

        for s in raw_sources:
            if isinstance(s, dict):
                src = ResearchSource.from_dict(s)
            elif isinstance(s, ResearchSource):
                src = s
            else:
                continue

            # Security domain check
            domain = src.domain or self._extract_domain(src.url_or_path)
            if domain in self.FORBIDDEN_DOMAINS:
                src.is_valid = False
                src.validation_notes = f"Forbidden domain '{domain}'"
                src.reliability_score = 0.0
            elif not src.snippet and not src.url_or_path:
                src.is_valid = False
                src.validation_notes = "Empty source content and URL"
            else:
                src.is_valid = True
                src.validation_notes = "Source validated successfully"

            validated.append(src.to_dict())

        return {
            "total_validated": len(validated),
            "valid_count": sum(1 for v in validated if v["is_valid"]),
            "validated_sources": validated,
        }

    def synthesize_results(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize findings from validated research sources."""
        raw_sources = payload.get("sources", [])
        query = payload.get("query", "General Query")

        findings: List[str] = []
        valid_sources = []

        for s in raw_sources:
            if isinstance(s, dict) and s.get("is_valid", True):
                snippet = s.get("snippet", "").strip()
                title = s.get("title", "Source")
                if snippet:
                    findings.append(f"[{title}]: {snippet}")
                    valid_sources.append(s)

        if findings:
            summary = f"Synthesized {len(findings)} key findings for query '{query}':\n"
            summary += "\n".join([f"- {f}" for f in findings])
        else:
            summary = f"No validated findings available for query '{query}'."

        return {
            "query": query,
            "findings_count": len(findings),
            "findings": findings,
            "summary": summary,
            "valid_sources_count": len(valid_sources),
        }

    def generate_research_artifact(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a structured research report artifact and register it
        with ArtifactRegistry.
        """
        title = payload.get("title", "Research Report")
        query = payload.get("query", "N/A")
        summary = payload.get("summary", "")
        findings = payload.get("findings", [])
        sources = payload.get("sources", [])

        content = f"# {title}\n\n"
        content += f"**Query**: {query}\n"
        content += f"**Generated At**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += "## Summary\n"
        content += f"{summary}\n\n"
        content += "## Findings\n"
        for f in findings:
            content += f"- {f}\n"
        content += "\n## Sources\n"
        for s in sources:
            if isinstance(s, dict):
                content += f"- [{s.get('title', 'Link')}]({s.get('url_or_path', '#')}) (Reliability: {s.get('reliability_score', 1.0)})\n"

        artifact_id = f"art_res_{uuid.uuid4().hex[:8]}"

        # Store with ArtifactRegistry if bus available
        if self.bus and hasattr(self.bus, "register_artifact"):
            try:
                meta = ArtifactMetadata(
                    artifact_id=artifact_id,
                    name=f"{title}.md",
                    artifact_type="markdown",
                    creator_id=self.agent_id,
                    content_hash=str(hash(content)),
                    size_bytes=len(content.encode("utf-8")),
                )
                self.bus.register_artifact(meta, content.encode("utf-8"))
            except Exception as err:
                logger.debug(f"[{self.name}] Artifact registration notice: {err}")

        return {
            "artifact_id": artifact_id,
            "title": title,
            "content_length": len(content),
            "content": content,
        }

    def conduct_research(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        High-level orchestrating method combining retrieval, collection,
        validation, synthesis, and artifact generation.
        """
        query = payload.get("query", "")
        r_task_res = self.create_research_task(payload)
        r_id = r_task_res["research_id"]

        with self._task_lock:
            if r_id in self._research_tasks:
                self._research_tasks[r_id].status = ResearchTaskStatus.IN_PROGRESS

        # Step 1: Retrieval
        ret_res = self.retrieve_information(payload)
        if not ret_res.get("available", True):
            with self._task_lock:
                if r_id in self._research_tasks:
                    self._research_tasks[r_id].status = ResearchTaskStatus.FAILED
            return ret_res

        # Step 2: Collection
        coll_res = self.collect_sources({"research_id": r_id, "sources": ret_res.get("sources", [])})

        # Step 3: Validation
        val_res = self.validate_sources({"sources": ret_res.get("sources", [])})

        # Step 4: Synthesis
        synth_res = self.synthesize_results({
            "query": query,
            "sources": val_res.get("validated_sources", []),
        })

        # Step 5: Artifact Generation
        art_res = self.generate_research_artifact({
            "title": f"Research Report - {query}",
            "query": query,
            "summary": synth_res.get("summary", ""),
            "findings": synth_res.get("findings", []),
            "sources": val_res.get("validated_sources", []),
        })

        with self._task_lock:
            if r_id in self._research_tasks:
                task = self._research_tasks[r_id]
                task.status = ResearchTaskStatus.COMPLETED
                task.summary = synth_res.get("summary", "")
                task.findings = synth_res.get("findings", [])
                task.artifact_id = art_res.get("artifact_id")
                task.completed_at = time.time()

        return {
            "research_id": r_id,
            "query": query,
            "summary": synth_res.get("summary", ""),
            "findings_count": len(synth_res.get("findings", [])),
            "artifact_id": art_res.get("artifact_id"),
            "status": ResearchTaskStatus.COMPLETED.value,
        }

    def cancel_research(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel an ongoing or recorded research task."""
        r_id = payload.get("research_id")
        with self._task_lock:
            if r_id in self._research_tasks:
                task = self._research_tasks[r_id]
                task.status = ResearchTaskStatus.CANCELLED
                return {"research_id": r_id, "status": ResearchTaskStatus.CANCELLED.value}
        return {"research_id": r_id, "status": "NOT_FOUND"}

    def query_research_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Query the status of a specific research task or all tasks."""
        r_id = payload.get("research_id")
        with self._task_lock:
            if r_id and r_id in self._research_tasks:
                return {"research_id": r_id, "task": self._research_tasks[r_id].to_dict()}
            return {
                "total_tasks": len(self._research_tasks),
                "tasks": [t.to_dict() for t in self._research_tasks.values()],
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
    def _extract_domain(url_or_path: str) -> str:
        """Extract domain name or local prefix from URL or path."""
        if not url_or_path:
            return "unknown"
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            match = re.search(r"https?://([^/]+)", url_or_path)
            return match.group(1).lower() if match else "web"
        return "local_file"
