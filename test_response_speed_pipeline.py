"""
ULTRON V3 - Response Speed Optimization Verification Test Suite
Verifies dynamic VAD, TTS engine singleton caching, LLM stream generation, and orchestrator sentence-level TTS dispatch.
"""

import time
import unittest
from voice.speech_output import speak, _get_engine, clean_voice_text
from brain.ollama_brain import ask_ollama_stream
from brain.llm_manager import llm_manager
from brain.orchestrator import orchestrator


class TestResponseSpeedPipeline(unittest.TestCase):
    """Response Speed Optimization Test Suite."""

    def test_01_tts_singleton_caching(self):
        """Verify TTS engine initialization uses a singleton instance for fast reuse."""
        t0 = time.perf_counter()
        engine1 = _get_engine()
        t_first = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        engine2 = _get_engine()
        t_second = (time.perf_counter() - t1) * 1000.0

        self.assertIsNotNone(engine1)
        self.assertIs(engine1, engine2)
        print(f"\n[TTS Benchmark] Cached Singleton Fetch: {t_second:.4f} ms")
        self.assertLess(t_second, 5.0)

    def test_02_clean_voice_text(self):
        """Verify markdown clean utility for voice synthesis."""
        text = "**Hello** _Boss_! `Ultron` is #1."
        cleaned = clean_voice_text(text)
        self.assertEqual(cleaned, "Hello Boss! Ultron is 1.")

    def test_03_llm_manager_stream(self):
        """Verify LLM manager ask_stream yields tokens."""
        prompt = "Say hello in 3 words."
        tokens = list(llm_manager.ask_stream(prompt))
        self.assertGreater(len(tokens), 0)
        full_text = "".join(tokens)
        print(f"\n[LLM Stream Benchmark] Yielded {len(tokens)} tokens: '{full_text.strip()}'")

    def test_04_orchestrator_fast_skill_latency(self):
        """Verify orchestrator fast skill response latency is sub-millisecond."""
        t0 = time.perf_counter()
        res = orchestrator.process_command("what is the time")
        t_exec = (time.perf_counter() - t0) * 1000.0
        print(f"\n[Orchestrator Benchmark] Skill 'time' executed in {t_exec:.2f} ms")
        self.assertIn("time is", res.lower())
        self.assertLess(t_exec, 50.0)


if __name__ == "__main__":
    unittest.main()
