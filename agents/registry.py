"""
ULTRON V3 - Agent Registry
Self-registering dynamic agent registry stub.
"""

from typing import Dict, Type, Optional
from agents.base_agent import BaseAgent
from core.logger import logger


class AgentRegistry:
    """Registry managing available Ultron agents."""

    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent_cls: Type[BaseAgent]) -> Type[BaseAgent]:
        """Decorator or direct call to register an agent class."""
        instance = agent_cls()
        name = instance.name.lower()
        self._agents[name] = instance
        logger.info(f"Agent '{instance.name}' registered successfully.")
        return agent_cls

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Fetch registered agent instance by name."""
        return self._agents.get(name.lower())

    def list_agents(self) -> Dict[str, str]:
        """Return dict of registered agent names and descriptions."""
        return {name: agent.description for name, agent in self._agents.items()}


# Global Agent Registry Singleton
agent_registry = AgentRegistry()
