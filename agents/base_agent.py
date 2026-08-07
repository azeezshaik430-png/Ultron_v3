"""
ULTRON V3 - Base Agent Interface
Abstract Base Class for future autonomous agents.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseAgent(ABC):
    """Abstract Base Class for all registered Ultron agents."""

    name: str = "BaseAgent"
    description: str = "Abstract agent interface"

    @abstractmethod
    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute agent task and return string result."""
        pass
