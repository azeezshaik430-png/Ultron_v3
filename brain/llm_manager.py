"""
ULTRON V3 - LLM Manager
Unified provider-agnostic interface for AI model execution.
Supports switching model providers via configuration without changing calling logic.
"""

from typing import Dict, Any, Callable, Generator
from core.config import config
from core.logger import logger
from brain.ollama_brain import ask_ollama, ask_ollama_stream


class LLMManager:
    """Multi-Provider AI Model Manager."""

    def __init__(self) -> None:
        self._providers: Dict[str, Callable[[str], str]] = {}
        self._stream_providers: Dict[str, Callable[[str], Generator[str, None, None]]] = {}
        # Register default initial provider (Ollama)
        self.register_provider("ollama", ask_ollama, ask_ollama_stream)

    def register_provider(
        self,
        name: str,
        handler: Callable[[str], str],
        stream_handler: Callable[[str], Generator[str, None, None]] = None,
    ) -> None:
        """Register a model provider driver function and optional streaming handler."""
        provider_key = name.lower()
        self._providers[provider_key] = handler
        if stream_handler:
            self._stream_providers[provider_key] = stream_handler
        logger.info(f"Registered LLM Provider: '{name}' (streaming: {stream_handler is not None})")

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

    def ask_stream(self, prompt: str, provider: str = None) -> Generator[str, None, None]:
        """Query active LLM provider with prompt and yield streaming token chunks."""
        target_provider = (provider or config.DEFAULT_LLM_PROVIDER).lower()

        if target_provider not in self._stream_providers:
            logger.warning(
                f"Stream provider '{target_provider}' not registered. Fallback to non-stream ask."
            )
            yield self.ask(prompt, provider=target_provider)
            return

        stream_handler = self._stream_providers[target_provider]
        try:
            logger.debug(f"Calling LLM Stream Provider '{target_provider}' with prompt: {prompt[:50]}...")
            for chunk in stream_handler(prompt):
                yield chunk
        except Exception as e:
            logger.error(f"LLM Stream Provider '{target_provider}' error: {e}")
            yield f"AI Model Error: {e}"


# Global LLM Manager Singleton
llm_manager = LLMManager()
