"""
ULTRON V3 - Partial Features Completion Test Suite
Tests for:
1. Orchestrator -> AgentManager & Domain Agent Runtime Dispatch (P0.1)
2. Voice Interruption & Barge-in (P1.1)
3. LLM Streaming & Provider Fallback (P1.2)
4. Canonical Semantic Memory Vector Ranking (P1.3)
"""

import os
import time
import shutil
import tempfile
import unittest
from typing import Generator

from brain.orchestrator import Orchestrator
from brain.agent_bus import AgentMemoryBus
from brain.agent_manager import AgentManager
from brain.llm_manager import LLMManager
from brain.semantic_memory import SemanticMemoryStore, LocalVectorEmbeddingProvider
from agents.memory_agent import MemoryAgent
from voice.speech_output import speak, speaking, stop_speaking
from voice.speech_input import listen


class TestPartialFeaturesCompletion(unittest.TestCase):
    """Integration and Unit Verification Suite for Completed Partial Features."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="ultron_partial_test_")
        self.bus = AgentMemoryBus()
        self.bus.initialize()
        self.agent_manager = AgentManager(bus=self.bus)
        self.agent_manager.initialize()
        self.orchestrator = Orchestrator(bus=self.bus, agent_manager=self.agent_manager)

    def tearDown(self) -> None:
        try:
            if hasattr(self, "orchestrator") and self.orchestrator:
                self.orchestrator.shutdown()
        except Exception:
            pass
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. ORCHESTRATOR -> AGENT SYSTEM INTEGRATION TESTS (P0.1)
    # =========================================================================

    def test_01_orchestrator_agent_manager_initialization(self) -> None:
        """Verify Orchestrator initializes AgentManager and registers all 6 domain agents."""
        agents = self.orchestrator.agent_manager.list_agents()
        self.assertGreaterEqual(len(agents), 6)
        agent_ids = [a["agent_id"] for a in agents]
        self.assertIn("system_agent", agent_ids)
        self.assertIn("memory_agent", agent_ids)
        self.assertIn("background_task_agent", agent_ids)
        self.assertIn("planning_agent", agent_ids)
        self.assertIn("research_agent", agent_ids)
        self.assertIn("coding_agent", agent_ids)

    def test_02_orchestrator_research_agent_dispatch(self) -> None:
        """Verify user research prompt dispatches to ResearchAgent via AgentManager."""
        res = self.orchestrator.process_command("research ULTRON V3 Architecture")
        self.assertIsNotNone(res)
        self.assertTrue("Research complete" in res or "Research completed" in res or "notice" in res)

    def test_03_orchestrator_coding_agent_dispatch(self) -> None:
        """Verify user coding prompt dispatches to CodingAgent via AgentManager."""
        res = self.orchestrator.process_command("generate python code factorial")
        self.assertIsNotNone(res)
        self.assertIn("Coding Agent", res)

    def test_04_orchestrator_planning_agent_dispatch(self) -> None:
        """Verify planning prompt dispatches to PlanningAgent via AgentManager."""
        res = self.orchestrator.process_command("create execution plan for system update")
        self.assertIsNotNone(res)
        self.assertIn("Plan", res)

    def test_05_orchestrator_system_agent_diagnostics_dispatch(self) -> None:
        """Verify system diagnostics prompt dispatches to SystemAgent via AgentManager."""
        res = self.orchestrator.process_command("agent status")
        self.assertIsNotNone(res)
        self.assertIn("healthy and operational", res)

    # =========================================================================
    # 2. VOICE INTERRUPTION / BARGE-IN TESTS (P1.1)
    # =========================================================================

    def test_06_voice_speaking_state_and_stop_speaking(self) -> None:
        """Verify thread-safe speaking flag and responsive stop_speaking interruption."""
        self.assertFalse(speaking())
        stop_speaking()
        self.assertFalse(speaking())

    def test_07_speech_input_auto_interrupts_ongoing_tts(self) -> None:
        """Verify listen() automatically invokes stop_speaking() if TTS is active."""
        from voice.speech_output import _speaking_flag
        _speaking_flag.set()
        self.assertTrue(speaking())
        # Call listen silently in mock context
        listen(silent=True)
        self.assertFalse(speaking())

    # =========================================================================
    # 3. LLM STREAMING & PROVIDER FALLBACK TESTS (P1.2)
    # =========================================================================

    def test_08_llm_manager_stream_tokens(self) -> None:
        """Verify ask_stream yields token chunks incrementally."""
        mgr = LLMManager()

        def dummy_stream(prompt: str) -> Generator[str, None, None]:
            yield "Hello "
            yield "Boss "
            yield "from ULTRON."

        mgr.register_provider("mock_stream", lambda p: "Hello Boss", stream_handler=dummy_stream)
        tokens = list(mgr.ask_stream("hi", provider="mock_stream"))
        self.assertEqual(tokens, ["Hello ", "Boss ", "from ULTRON."])

    def test_09_llm_manager_stream_sentences(self) -> None:
        """Verify ask_stream_sentences buffers token stream into full sentence chunks for low TTFS."""
        mgr = LLMManager()

        def sentence_stream(prompt: str) -> Generator[str, None, None]:
            yield "ULTRON "
            yield "is "
            yield "online. "
            yield "All "
            yield "systems "
            yield "ready!"

        mgr.register_provider("mock_sentences", lambda p: "Full text", stream_handler=sentence_stream)
        sentences = list(mgr.ask_stream_sentences("hello", provider="mock_sentences"))
        self.assertEqual(sentences, ["ULTRON is online.", "All systems ready!"])

    def test_10_llm_manager_provider_fallback(self) -> None:
        """Verify LLMManager falls back gracefully when primary provider fails."""
        mgr = LLMManager()

        def failing_driver(prompt: str) -> str:
            raise RuntimeError("Primary provider connection timeout")

        def working_fallback(prompt: str) -> str:
            return "Fallback LLM Response"

        mgr.register_provider("failing_p1", failing_driver)
        mgr.register_provider("ollama", working_fallback)

        res = mgr.ask("test query", provider="failing_p1")
        self.assertEqual(res, "Fallback LLM Response")

    # =========================================================================
    # 4. CANONICAL SEMANTIC MEMORY VECTOR TESTS (P1.3)
    # =========================================================================

    def test_11_local_vector_embedding_provider(self) -> None:
        """Verify LocalVectorEmbeddingProvider generates normalized 128-d vectors."""
        embedder = LocalVectorEmbeddingProvider(vector_dim=128)
        vec = embedder.get_embedding("ULTRON V3 Architecture")
        self.assertEqual(len(vec), 128)
        # Check normalization
        norm = sum(v * v for v in vec)
        self.assertAlmostEqual(norm, 1.0, places=2)

    def test_12_semantic_memory_store_cosine_ranking(self) -> None:
        """Verify SemanticMemoryStore ranks memories by cosine similarity relevance score."""
        store_path = os.path.join(self.test_dir, "sem_mem.json")
        store = SemanticMemoryStore(store_path=store_path)

        store.store_memory("favorite_game", "Cyberpunk 2077")
        store.store_memory("laptop_brand", "ASUS ROG Strix")
        store.store_memory("favorite_food", "Italian Pizza")

        results = store.query_semantic_memory("What video game do I play?", top_k=2)
        self.assertGreater(len(results), 0)
        top_match = results[0]
        self.assertEqual(top_match["key"], "favorite_game")
        self.assertGreater(top_match["relevance_score"], 0.0)

    def test_13_memory_agent_semantic_search_integration(self) -> None:
        """Verify MemoryAgent capability query_semantic_memory operates end-to-end."""
        agent = MemoryAgent(bus=self.bus)
        agent.initialize()

        agent.execute_task("task_mem_s1", {
            "action": "store_memory",
            "key": "project_name",
            "value": "ULTRON Autonomous Assistant",
        })

        res = agent.execute_task("task_mem_s2", {
            "action": "query_semantic_memory",
            "query": "What project am I building?",
            "top_k": 3,
        })

        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("results", res["result"])
        self.assertGreater(res["result"]["count"], 0)


if __name__ == "__main__":
    unittest.main()
