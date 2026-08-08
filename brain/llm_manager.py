from typing import Dict, Any, Callable, Generator
import re
from core.config import config
from core.logger import logger
from brain.ollama_brain import ask_ollama, ask_ollama_stream


class LLMManager:
    """Multi-Provider AI Model Manager with Streaming & Fallback."""

    def __init__(self) -> None:
        self._providers: Dict[str, Callable[[str], str]] = {}
        self._stream_providers: Dict[str, Callable[[str], Generator[str, None, None]]] = {}
        self._fallback_order = ["ollama"]

        # Register default initial provider (Ollama)
        self.register_provider("ollama", ask_ollama, stream_handler=ask_ollama_stream)

    def register_provider(
        self,
        name: str,
        handler: Callable[[str], str],
        stream_handler: Callable[[str], Generator[str, None, None]] = None,
    ) -> None:
        """Register a model provider driver function."""
        p_name = name.lower().strip()
        self._providers[p_name] = handler
        if stream_handler:
            self._stream_providers[p_name] = stream_handler
        logger.info(f"Registered LLM Provider: '{p_name}' (Stream: {stream_handler is not None})")

    def ask(self, prompt: str, provider: str = None) -> str:
        """Query active LLM provider with prompt and return text response with fallback."""
        primary = (provider or config.DEFAULT_LLM_PROVIDER).lower().strip()
        providers_to_try = [primary] + [p for p in self._fallback_order if p != primary]

        last_error = None
        for p_name in providers_to_try:
            if p_name not in self._providers:
                continue

            handler = self._providers[p_name]
            try:
                logger.debug(f"Calling LLM Provider '{p_name}' with prompt: {prompt[:50]}...")
                res = handler(prompt)
                if res and not str(res).startswith("AI Model Error:") and not str(res).startswith("Ollama error:"):
                    return res
                last_error = res
            except Exception as e:
                last_error = str(e)
                logger.warning(f"LLM Provider '{p_name}' failed: {e}. Trying fallback...")

        logger.error(f"All configured LLM providers failed. Last error: {last_error}")
        return f"AI Model Error: All providers unavailable ({last_error})"

    def ask_stream(self, prompt: str, provider: str = None) -> Generator[str, None, None]:
        """Yield token chunks incrementally from active provider with fallback."""
        primary = (provider or config.DEFAULT_LLM_PROVIDER).lower().strip()
        providers_to_try = [primary] + [p for p in self._fallback_order if p != primary]

        for p_name in providers_to_try:
            if p_name in self._stream_providers:
                handler = self._stream_providers[p_name]
                try:
                    logger.debug(f"Streaming from LLM Provider '{p_name}'...")
                    tokens_yielded = False
                    for token in handler(prompt):
                        tokens_yielded = True
                        yield token
                    if tokens_yielded:
                        return
                except Exception as e:
                    logger.warning(f"Streaming LLM Provider '{p_name}' failed: {e}. Trying fallback...")

        # Fallback to non-streaming ask if stream handler failed
        res = self.ask(prompt, provider=provider)
        yield res

    def ask_stream_sentences(self, prompt: str, provider: str = None) -> Generator[str, None, None]:
        """Buffer streamed tokens into full sentences for low TTFS audio synthesis."""
        buffer = ""
        sentence_regex = re.compile(r'(?<=[.!?])\s+|\n+')

        for token in self.ask_stream(prompt, provider=provider):
            buffer += token
            match = sentence_regex.search(buffer)
            while match:
                idx = match.end()
                sentence = buffer[:idx].strip()
                buffer = buffer[idx:]
                if sentence:
                    yield sentence
                match = sentence_regex.search(buffer)

        if buffer.strip():
            yield buffer.strip()


# Global LLM Manager Singleton
llm_manager = LLMManager()
