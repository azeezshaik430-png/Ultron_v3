"""
ULTRON V3 - Canonical Semantic Memory Engine
Zero-dependency vector store with Cosine Similarity relevance ranking and embedding provider fallback.
"""

import os
import json
import math
import uuid
import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from core.config import config
from core.logger import logger


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding drivers."""

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Generate numerical vector embedding for input text."""
        pass


class LocalVectorEmbeddingProvider(EmbeddingProvider):
    """
    Zero-dependency TF-IDF / N-gram character & word frequency vectorizer.
    Generates normalized 128-dimensional embedding vectors using deterministic hashing.
    """

    def __init__(self, vector_dim: int = 128) -> None:
        self.vector_dim = vector_dim

    def get_embedding(self, text: str) -> List[float]:
        import zlib
        if not text or not text.strip():
            return [0.0] * self.vector_dim

        vec = [0.0] * self.vector_dim
        # Clean punctuation to improve token matching (e.g. matching "game" to "favorite_game:")
        cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower())
        words = cleaned.split()

        # Word & character 3-gram feature hashing using deterministic Adler-32
        for word in words:
            # Word hashing
            h_val = zlib.adler32(word.encode('utf-8')) % self.vector_dim
            vec[h_val] += 1.0

            # Character tri-gram hashing
            for i in range(len(word) - 2):
                gram = word[i : i + 3]
                g_val = zlib.adler32(gram.encode('utf-8')) % self.vector_dim
                vec[g_val] += 0.5

        # L2 Normalization
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [round(v / norm, 6) for v in vec]

        return vec


class SemanticMemoryStore:
    """
    Canonical Semantic Memory Store for ULTRON V3.
    Stores memories with vector embeddings and evaluates query similarity using Cosine Similarity.
    """

    def __init__(
        self,
        store_path: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.store_path = store_path or os.path.join(config.DATA_DIR, "semantic_memory.json")
        self.embedding_provider = embedding_provider or LocalVectorEmbeddingProvider()
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        with self._lock:
            if os.path.exists(self.store_path):
                try:
                    with open(self.store_path, "r", encoding="utf-8") as f:
                        self._entries = json.load(f)
                except Exception as err:
                    logger.error(f"[SemanticMemoryStore] Load error: {err}")
                    self._entries = []
            else:
                self._entries = []

    def _save(self) -> None:
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
                with open(self.store_path, "w", encoding="utf-8") as f:
                    json.dump(self._entries, f, indent=2)
            except Exception as err:
                logger.error(f"[SemanticMemoryStore] Save error: {err}")

    def store_memory(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Vectorize and store a new memory entry."""
        with self._lock:
            mem_id = f"sem_{uuid.uuid4().hex[:8]}"
            text_representation = f"{key}: {value}"
            embedding = self.embedding_provider.get_embedding(text_representation)

            entry = {
                "memory_id": mem_id,
                "key": key,
                "value": value,
                "text": text_representation,
                "embedding": embedding,
                "metadata": metadata or {},
                "timestamp": time.time(),
            }

            # Update existing entry if key exists
            for idx, existing in enumerate(self._entries):
                if existing.get("key") == key:
                    self._entries[idx] = entry
                    self._save()
                    return mem_id

            self._entries.append(entry)
            self._save()
            return mem_id

    def query_semantic_memory(
        self, query: str, top_k: int = 5, min_score: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Query memory using cosine similarity score ranking."""
        with self._lock:
            if not query or not self._entries:
                return []

            q_vec = self.embedding_provider.get_embedding(query)
            scored_results: List[Tuple[float, Dict[str, Any]]] = []

            for entry in self._entries:
                e_vec = entry.get("embedding", [])
                score = self._cosine_similarity(q_vec, e_vec)
                if score >= min_score:
                    item = {
                        "memory_id": entry["memory_id"],
                        "key": entry["key"],
                        "value": entry["value"],
                        "relevance_score": round(score, 4),
                        "metadata": entry.get("metadata", {}),
                    }
                    scored_results.append((score, item))

            scored_results.sort(key=lambda x: x[0], reverse=True)
            return [item for _, item in scored_results[:top_k]]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def clear(self) -> None:
        """Clear all semantic memory entries."""
        with self._lock:
            self._entries = []
            self._save()
