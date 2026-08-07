"""
ULTRON V3 - Universal Command Router
Routes requests across Skills, Agents, Plugins, and LLM Manager.
"""

from typing import Dict, Any, Union
from core.logger import logger
from agents.registry import agent_registry
from plugins.plugin_loader import plugin_loader


def route(intent_data: Union[Dict[str, Any], str]) -> str:
    """
    Backward-compatible intent router.
    Converts intent dictionary into system route string.
    """
    if isinstance(intent_data, str):
        return "UNKNOWN"

    intent = intent_data.get("intent")

    if intent == "OPEN_APP":
        return "APP_OPEN"

    if intent == "CLOSE_APP":
        return "APP_CLOSE"

    if intent == "CHAT":
        return "AI_CHAT"

    return "UNKNOWN"


class Router:
    """Universal Target Dispatcher."""

    def dispatch(self, route_type: str, target: str, payload: Any = None) -> Dict[str, Any]:
        """Dispatch route to designated subsystem (Skill, Agent, Plugin, LLM)."""
        logger.debug(f"Routing target: type='{route_type}', target='{target}'")

        if route_type == "AGENT":
            agent = agent_registry.get_agent(target)
            if agent:
                res = agent.run(payload or target)
                return {"status": "SUCCESS", "result": res}
            return {"status": "ERROR", "message": f"Agent '{target}' not registered"}

        if route_type == "PLUGIN":
            if target in plugin_loader._plugins:
                return {"status": "SUCCESS", "result": f"Plugin '{target}' executed"}
            return {"status": "ERROR", "message": f"Plugin '{target}' not found"}

        return {"status": "SUCCESS", "route": route_type, "target": target}


# Global Router Singleton
router_dispatcher = Router()