"""
ULTRON V3 - LLM Manager
Unified provider-agnostic interface for AI model execution.
Supports switching model providers via configuration without changing calling logic.
"""

from typing import Dict, Any, Callable
from core.config import config
from core.logger import logger
from brain.ollama_brain import ask_ollama


class LLMManager:
    """Multi-Provider AI Model Manager."""

    def __init__(self) -> None:
        self._providers: Dict[str, Callable[[str], str]] = {}
        # Register default initial provider (Ollama)
        self.register_provider("ollama", ask_ollama)

    def register_provider(self, name: str, handler: Callable[[str], str]) -> None:
        """Register a model provider driver function."""
        self._providers[name.lower()] = handler
        logger.info(f"Registered LLM Provider: '{name}'")

    def ask(self, prompt: str, provider: str = None) -> str:
        """Query active LLM provider with prompt and return text response."""
        target_provider = (provider or config.DEFAULT_LLM_PROVIDER).lower()

        if target_provider not in self._providers:
            logger.warning(
                f"Provider '{target_provider}' not registered. Fallback to 'ollama'."
            )
            target_provider = "ollama"

        handler = self._providers[target_provider]
        try:
            logger.debug(f"Calling LLM Provider '{target_provider}' with prompt: {prompt[:50]}...")
            return handler(prompt)
        except Exception as e:
            logger.error(f"LLM Provider '{target_provider}' error: {e}")
            return f"AI Model Error: {e}"


# Global LLM Manager Singleton
llm_manager = LLMManager()
