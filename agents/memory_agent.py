"""
ULTRON V3 - Memory / Knowledge Agent
Phase 2B.2 Memory Knowledge Agent.
Integrates existing memory.json / brain.memory with Phase 2A AgentMemoryBus, WorkspaceStore, WorkspaceACL, TransactionManager, and Scratchpad.
"""

from typing import Dict, Any, Optional, List
from agents.base_ultron_agent import BaseUltronAgent
import brain.memory as memory_sys
from brain.semantic_memory import SemanticMemoryStore
from core.logger import logger


class MemoryAgent(BaseUltronAgent):
    """
    Memory & Knowledge Domain Agent with Canonical Semantic Retrieval.
    """

    def __init__(
        self,
        agent_id: str = "memory_agent",
        name: str = "Memory Knowledge Agent",
        description: str = "Manages persistent user memories, semantic vector retrieval, structured queries, and workspace memory sync.",
        bus: Optional[Any] = None,
        version: str = "1.1.0",
    ) -> None:
        capabilities = [
            "store_memory",
            "retrieve_memory",
            "update_memory",
            "delete_memory",
            "search_knowledge",
            "structured_query",
            "query_semantic_memory",
            "rank_relevance",
        ]
        supported_skills = [
            "memory_store",
            "memory_recall",
            "semantic_search",
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
        self.semantic_store = SemanticMemoryStore()

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        """
        Execute memory domain payload.
        Payload structure:
        {
            "action": str,         # "store", "retrieve", "update", "delete", "search", "structured_query"
            "key": str,            # memory key
            "value": Any,          # memory value
            "query": str,          # search term
            "sensitive": bool,     # flag if memory is marked sensitive
            ...
        }
        """
        if not isinstance(payload, dict):
            task_str = str(payload)
            return self._handle_raw_string_task(task_str)

        action = payload.get("action", "").lower().strip()
        if not action:
            cmd = payload.get("task") or payload.get("command") or ""
            if cmd:
                return self._handle_raw_string_task(str(cmd))
            raise ValueError("Payload missing required 'action' or 'task' field.")

        # ---------------------------------------------------------------------
        # 1. STORE MEMORY
        # ---------------------------------------------------------------------
        if action in ["store_memory", "store", "remember", "write"]:
            key = payload.get("key")
            value = payload.get("value")
            if not key:
                raise ValueError("store_memory requires 'key' parameter.")
            if payload.get("sensitive", False) and not payload.get("approved", True):
                return "Security block: Silent storage of sensitive information is prohibited without approval."

            # A. Save to persistent memory.json via brain.memory
            mem_msg = memory_sys.remember(key, value)

            # B. Sync to WorkspaceStore via AgentMemoryBus (subject to ACL)
            ws_key = f"workspace/{self.agent_id}/memories/{key}"
            try:
                self.write_workspace(ws_key, value)
            except Exception as err:
                logger.debug(f"[{self.name}] Workspace sync notice for key '{ws_key}': {err}")

            # C. Sync to SemanticMemoryStore for vector similarity ranking
            try:
                self.semantic_store.store_memory(key, value)
            except Exception as err:
                logger.debug(f"[{self.name}] Semantic store sync notice: {err}")

            return {
                "key": key,
                "value": value,
                "message": mem_msg,
                "workspace_key": ws_key,
            }

        # ---------------------------------------------------------------------
        # 2. RETRIEVE MEMORY
        # ---------------------------------------------------------------------
        elif action in ["retrieve_memory", "retrieve", "recall", "read"]:
            key = payload.get("key")
            if not key:
                raise ValueError("retrieve_memory requires 'key' parameter.")

            # A. Recall from memory.json
            val = memory_sys.recall(key)

            # B. Fallback to WorkspaceStore if not found in memory.json
            if val is None:
                ws_key = f"workspace/{self.agent_id}/memories/{key}"
                try:
                    val = self.read_workspace(ws_key)
                except Exception:
                    val = None

            return {
                "key": key,
                "value": val,
                "found": val is not None,
            }

        # ---------------------------------------------------------------------
        # 3. UPDATE MEMORY
        # ---------------------------------------------------------------------
        elif action in ["update_memory", "update", "modify"]:
            key = payload.get("key")
            value = payload.get("value")
            if not key:
                raise ValueError("update_memory requires 'key' parameter.")

            mem_data = memory_sys.load_memory()
            exists = key in mem_data
            memory_sys.remember(key, value)
            try:
                self.semantic_store.store_memory(key, value)
            except Exception:
                pass

            return {
                "key": key,
                "value": value,
                "updated": exists,
            }

        # ---------------------------------------------------------------------
        # 4. DELETE MEMORY
        # ---------------------------------------------------------------------
        elif action in ["delete_memory", "delete", "forget"]:
            key = payload.get("key")
            if not key:
                raise ValueError("delete_memory requires 'key' parameter.")

            mem_data = memory_sys.load_memory()
            existed = key in mem_data
            if existed:
                del mem_data[key]
                memory_sys.save_memory(mem_data)

            return {
                "key": key,
                "deleted": existed,
                "message": f"Memory '{key}' deleted." if existed else f"Memory '{key}' not found.",
            }

        # ---------------------------------------------------------------------
        # 5. SEARCH KNOWLEDGE
        # ---------------------------------------------------------------------
        elif action in ["search_knowledge", "search", "query"]:
            query = (payload.get("query") or payload.get("term") or "").lower().strip()
            if not query:
                raise ValueError("search_knowledge requires 'query' parameter.")

            mem_data = memory_sys.load_memory()
            matches = {}
            for k, v in mem_data.items():
                if query in str(k).lower() or query in str(v).lower():
                    matches[k] = v

            return {
                "query": query,
                "count": len(matches),
                "results": matches,
            }

        # ---------------------------------------------------------------------
        # 6. STRUCTURED QUERY FOR ORCHESTRATOR
        # ---------------------------------------------------------------------
        elif action in ["structured_query", "get_all", "dump_memories"]:
            mem_data = memory_sys.load_memory()
            return {
                "total_entries": len(mem_data),
                "memories": mem_data,
            }

        # ---------------------------------------------------------------------
        # 7. QUERY SEMANTIC MEMORY & RELEVANCE RANKING
        # ---------------------------------------------------------------------
        elif action in ["query_semantic_memory", "rank_relevance", "semantic_search"]:
            query = payload.get("query") or payload.get("term") or ""
            top_k = int(payload.get("top_k", 5))
            min_score = float(payload.get("min_score", 0.05))

            if not query:
                raise ValueError("query_semantic_memory requires 'query' parameter.")

            results = self.semantic_store.query_semantic_memory(query, top_k=top_k, min_score=min_score)
            return {
                "query": query,
                "count": len(results),
                "results": results,
            }

        else:
            raise ValueError(f"Unknown or unsupported memory action: '{action}'")

    def _handle_raw_string_task(self, task_str: str) -> str:
        """Helper for raw string memory commands."""
        task_lower = task_str.lower().strip()
        if task_lower.startswith("remember "):
            parts = task_str[9:].split(" is ", 1)
            if len(parts) == 2:
                return memory_sys.remember(parts[0].strip(), parts[1].strip())
            return memory_sys.remember(parts[0].strip(), "true")
        elif task_lower.startswith("recall "):
            key = task_str[7:].strip()
            val = memory_sys.recall(key)
            return f"{key} is {val}" if val is not None else f"I don't remember {key}."
        elif task_lower == "clear memories":
            return memory_sys.clear_memory()
        else:
            return f"MemoryAgent received task: '{task_str}'"
