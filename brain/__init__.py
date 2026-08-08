"""
ULTRON V3 - Brain Package
"""

def __getattr__(name):
    if name == 'Orchestrator':
        from brain.orchestrator import Orchestrator
        return Orchestrator
    elif name == 'orchestrator':
        from brain.orchestrator import orchestrator
        return orchestrator
    elif name == 'LLMManager':
        from brain.llm_manager import LLMManager
        return LLMManager
    elif name == 'llm_manager':
        from brain.llm_manager import llm_manager
        return llm_manager
    elif name == 'plan':
        from brain.planner import plan
        return plan
    elif name == 'route':
        from brain.router import route
        return route
    elif name == 'router_dispatcher':
        from brain.router import router_dispatcher
        return router_dispatcher
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    "Orchestrator",
    "orchestrator",
    "LLMManager",
    "llm_manager",
    "plan",
    "route",
    "router_dispatcher",
]
