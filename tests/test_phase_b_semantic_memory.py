"""
ULTRON V3 - Phase B Persistent Semantic Memory Unit & Integration Test Suite
Verifies end-to-end memory persistence, deterministic vector embeddings, thread safety,
upsert deduplication, corruption recovery, semantic context prompt injection, REST hydration, and WS events.
"""

import unittest
import os
import json
import shutil
import threading
import time
from fastapi.testclient import TestClient

from brain.semantic_memory import SemanticMemoryStore, LocalVectorEmbeddingProvider
import brain.memory as memory_sys
import brain.conversation_memory as chat_sys
from brain.smart_memory import extract_memory
from brain.ollama_brain import build_system_prompt
from core.event_bus import event_bus
from api.app import app
from api.websocket_manager import get_ws_manager


class TestPhaseBSemanticMemory(unittest.TestCase):

    def setUp(self):
        self.test_dir = "data/test_artifacts/phase_b"
        os.makedirs(self.test_dir, exist_ok=True)
        memory_sys.MEMORY_FILE = os.path.join(self.test_dir, "test_memory.json")
        chat_sys.CHAT_FILE = os.path.join(self.test_dir, "test_chat.json")
        self.sem_store_path = os.path.join(self.test_dir, "test_semantic.json")
        self.sem_store = SemanticMemoryStore(store_path=self.sem_store_path)
        memory_sys.clear_memory()

    def tearDown(self):
        memory_sys.clear_memory()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # A. Deterministic Embeddings
    # -------------------------------------------------------------------------
    def test_01_deterministic_embeddings(self):
        """A: Vector embeddings are 100% deterministic across instances."""
        provider1 = LocalVectorEmbeddingProvider()
        provider2 = LocalVectorEmbeddingProvider()
        text = "user favorite_game: Palworld"
        emb1 = provider1.get_embedding(text)
        emb2 = provider2.get_embedding(text)
        self.assertEqual(emb1, emb2)
        self.assertEqual(len(emb1), 128)

    # -------------------------------------------------------------------------
    # B. Semantic Vector Similarity Ranking
    # -------------------------------------------------------------------------
    def test_02_semantic_vector_ranking(self):
        """B: Semantic query similarity ranking returns correct top match."""
        self.sem_store.store_memory("favorite_game", "Palworld")
        self.sem_store.store_memory("laptop", "ThinkPad P16")
        self.sem_store.store_memory("favorite_movie", "Interstellar")

        results = self.sem_store.query_semantic_memory("what game do I enjoy playing?", top_k=1)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["key"], "favorite_game")
        self.assertEqual(results[0]["value"], "Palworld")

    # -------------------------------------------------------------------------
    # C. Natural-Language Extraction & Vector Sync
    # -------------------------------------------------------------------------
    def test_03_natural_language_extraction_canonical_path(self):
        """C: extract_memory updates both memory.json and SemanticMemoryStore."""
        res = extract_memory("my name is Azeez")
        self.assertIn("azeez", res.lower())

        # Verify key-value recall
        self.assertEqual(memory_sys.recall("name"), "azeez")

        # Verify semantic vector retrieval
        sem_res = SemanticMemoryStore().query_semantic_memory("what is my name?", top_k=1)
        self.assertGreater(len(sem_res), 0)
        self.assertEqual(sem_res[0]["key"], "name")
        self.assertEqual(sem_res[0]["value"], "azeez")

    # -------------------------------------------------------------------------
    # D & E. Deterministic Upsert & Idempotency
    # -------------------------------------------------------------------------
    def test_04_upsert_and_idempotency(self):
        """D & E: Updating key replaces semantic entry without duplicate growth."""
        store = SemanticMemoryStore(store_path=self.sem_store_path)
        store.store_memory("favorite_color", "blue")
        self.assertEqual(len(store._entries), 1)

        # Repeated remember calls update existing key
        store.store_memory("favorite_color", "emerald")
        self.assertEqual(len(store._entries), 1)
        self.assertEqual(store._entries[0]["value"], "emerald")

    # -------------------------------------------------------------------------
    # F. Concurrent Writes Safety
    # -------------------------------------------------------------------------
    def test_05_concurrent_writes_thread_safety(self):
        """F: Concurrent memory writes do not corrupt storage files."""
        def worker(thread_idx):
            for i in range(10):
                memory_sys.remember(f"thread_{thread_idx}_key_{i}", f"val_{i}")

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        loaded = memory_sys.load_memory()
        self.assertEqual(len(loaded), 40)

    # -------------------------------------------------------------------------
    # G. Restart Survival
    # -------------------------------------------------------------------------
    def test_06_memory_restart_survival(self):
        """G: Memory entries survive process re-initialization."""
        memory_sys.remember("city", "Hyderabad")

        # Simulate app restart by loading fresh dictionary
        loaded = memory_sys.load_memory()
        self.assertEqual(loaded.get("city"), "Hyderabad")

    # -------------------------------------------------------------------------
    # H. Corrupted JSON Resilience
    # -------------------------------------------------------------------------
    def test_07_corrupted_json_resilience(self):
        """H: Invalid JSON does not crash ULTRON and creates backup safely."""
        with open(memory_sys.MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write("{ invalid json content ...")

        # Load corrupted file -> returns empty dict, creates backup
        res = memory_sys.load_memory()
        self.assertEqual(res, {})
        self.assertTrue(os.path.exists(memory_sys.MEMORY_FILE + ".corrupted"))

    # -------------------------------------------------------------------------
    # I & J. Semantic Context Prompt Injection without Ollama
    # -------------------------------------------------------------------------
    def test_08_semantic_context_prompt_injection(self):
        """I & J: Prompt construction includes relevant semantic context without Ollama."""
        memory_sys.remember("laptop", "ThinkPad")
        SemanticMemoryStore().store_memory("hobby", "astrophotography")

        prompt_str = build_system_prompt("what camera equipment do I use for astrophotography?")
        self.assertIn("astrophotography", prompt_str)
        self.assertIn("User Memory:", prompt_str)

    # -------------------------------------------------------------------------
    # K & N. REST Memory API Hydration
    # -------------------------------------------------------------------------
    def test_09_rest_memory_api(self):
        """K & N: GET /api/memory returns bounded, ordered memory entries for UI."""
        memory_sys.remember("name", "Azeez")
        memory_sys.remember("favorite_game", "Palworld")

        client = TestClient(app)
        res = client.get("/api/memory?limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["memories"][0]["key"], "favorite_game")
        self.assertEqual(data["memories"][1]["key"], "name")

    # -------------------------------------------------------------------------
    # L & M. Backend Memory Event & WebSocket Stream
    # -------------------------------------------------------------------------
    def test_10_memory_event_and_websocket_stream(self):
        """L & M: Memory update emits MEMORY_UPDATED event and broadcasts over WS."""
        ws_manager = get_ws_manager()
        ws_manager._setup_agent_bus_bridge()
        received_events = []

        def mock_broadcast_sync(event_name, payload):
            received_events.append((event_name, payload))

        ws_manager.broadcast_sync = mock_broadcast_sync

        memory_sys.remember("favorite_framework", "FastAPI")
        time.sleep(0.1)

        mem_events = [payload for evt, payload in received_events if evt == "memory_updated"]
        self.assertGreaterEqual(len(mem_events), 1)
        self.assertEqual(mem_events[0]["key"], "favorite_framework")
        self.assertEqual(mem_events[0]["value"], "FastAPI")


if __name__ == "__main__":
    unittest.main()
