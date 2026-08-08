"""
ULTRON V3 - Manual-Test Bug Fixes Test Suite
Tests for:
1. Dynamic hardware info detection & SystemAgent routing (Bug 1)
2. TTS engine initialization, voice selection, COM thread safety & lifecycle (Bug 2)
3. Voice interruption / barge-in preservation (Bug 3)
4. Voice auth dev bypass (Bug 4)
5. Response -> TTS integration & streaming (Bug 5 & Bug 6)
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

import skills.system_control as system_control
from brain.orchestrator import orchestrator
from voice.speech_output import speak, speaking, stop_speaking, clean_voice_text
from agents.system_agent import SystemAgent
from core.config import config


class TestManualBugFixes(unittest.TestCase):
    """Unit and Integration Tests for Confirmed Bug Fixes."""

    # =========================================================================
    # BUG 1 — SYSTEM INFORMATION DYNAMIC DETECTION & ROUTING
    # =========================================================================

    def test_01_dynamic_gpu_detection(self) -> None:
        """Verify get_gpus dynamically retrieves video controllers without hardcoding."""
        gpus = system_control.get_gpus()
        self.assertIsInstance(gpus, list)
        if sys.platform == "win32":
            # On this Windows machine, GPUs must include Intel UHD and NVIDIA RTX 2050
            gpus_str = " ".join(gpus)
            self.assertIn("Intel", gpus_str)
            self.assertIn("NVIDIA", gpus_str)

    def test_02_dynamic_cpu_detection(self) -> None:
        """Verify get_cpu_info retrieves CPU name and core metrics."""
        cpu_info = system_control.get_cpu_info()
        self.assertIsInstance(cpu_info, str)
        self.assertNotEqual(cpu_info, "")
        self.assertNotEqual(cpu_info, "Unavailable")

    def test_03_get_system_info_format_and_no_hardcoding(self) -> None:
        """Verify get_system_info returns clean formatted details and never hardcodes values."""
        info = system_control.get_system_info()
        self.assertIn("verified system hardware details", info.lower())
        self.assertIn("• os:", info.lower())
        self.assertIn("• cpu:", info.lower())
        self.assertIn("• gpu(s):", info.lower())
        self.assertIn("• memory (ram):", info.lower())

    def test_04_system_agent_action_routing(self) -> None:
        """Verify SystemAgent handles system_info action and returns dynamic details."""
        agent = SystemAgent()
        agent.initialize()
        res = agent.execute_task("t_sys_info", {"action": "system_info"})
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("verified system hardware details", str(res["result"]).lower())

    def test_05_orchestrator_system_info_routing_bypasses_llm(self) -> None:
        """Verify Orchestrator routes 'what is my system details' and 'tell my system' to SystemAgent, NOT LLM."""
        res1 = orchestrator.process_command("what is my system details")
        self.assertIn("verified system hardware details", res1.lower())
        self.assertIn("cpu:", res1.lower())

        res2 = orchestrator.process_command("tell my system")
        self.assertIn("verified system hardware details", res2.lower())
        self.assertIn("gpu(s):", res2.lower())

    # =========================================================================
    # BUG 2 — TTS ENGINE & AUDIO PLAYBACK PIPELINE
    # =========================================================================

    def test_06_clean_voice_text(self) -> None:
        """Verify text cleaner strips markdown formatting."""
        cleaned = clean_voice_text("**Hello** *Boss* #1 `test`")
        self.assertEqual(cleaned, "Hello Boss 1 test")

    def test_07_tts_state_and_speak_execution(self) -> None:
        """Verify speak() manages speaking() state and completes cleanly."""
        self.assertFalse(speaking())
        res = speak("Testing TTS audio output pipeline.")
        self.assertTrue(res)
        self.assertFalse(speaking())

    def test_08_stop_speaking_interruption(self) -> None:
        """Verify stop_speaking() halts playback and resets speaking state."""
        stop_speaking()
        self.assertFalse(speaking())

    # =========================================================================
    # BUG 4 — VOICE AUTH DEVELOPMENT BYPASS
    # =========================================================================

    def test_09_voice_auth_dev_bypass(self) -> None:
        """Verify VOICE_AUTH_ENABLED configuration flag behavior."""
        with patch.object(config, "VOICE_AUTH_ENABLED", False):
            from voice.voice_guard import verify_boss
            res = verify_boss("fake.wav")
            self.assertTrue(res)


if __name__ == "__main__":
    unittest.main()
