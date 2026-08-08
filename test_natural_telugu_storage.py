"""
ULTRON V3 - Natural Conversation, Telugu Mode, & Storage Safety Test Suite
Tests for:
1. Natural Conversation (No automatic Boss prefix on general questions)
2. Language State & Telugu Mode Switching
3. Deterministic Storage Drive (D-drive / C-drive) Routing & Zero Hallucination
4. Piper ONNX Telugu Male Voice Synthesis (te_IN-venkatesh-medium)
5. Multi-Language TTS Routing (English SAPI5 David + Telugu Piper Venkatesh)
"""

import unittest
from unittest.mock import patch

from core.session import session
from brain.orchestrator import orchestrator
from agents.system_agent import SystemAgent
import skills.system_control as system_control
from voice.speech_output import speak, speaking, _get_piper_telugu_voice


class TestNaturalTeluguStorage(unittest.TestCase):
    """Unit and Integration Tests for Naturalness, Telugu, and Storage Safety."""

    def setUp(self) -> None:
        session.reset()
        session.preferred_language = "en"

    def tearDown(self) -> None:
        session.reset()

    # =========================================================================
    # 1. NATURAL CONVERSATION (NO FORCED "BOSS" PREFIX)
    # =========================================================================

    def test_01_natural_language_response_no_forced_boss_prefix(self) -> None:
        """Verify normal conversational answer does NOT automatically begin with 'Boss'."""
        res = orchestrator.process_command("What is Java?")
        self.assertIsInstance(res, str)
        self.assertFalse(res.startswith("Boss,"))
        self.assertFalse(res.startswith("Boss!"))

    def test_02_wake_greeting_preserves_boss(self) -> None:
        """Verify wake-word greeting maintains 'What can I do for you, Boss?'."""
        from voice.wake_listener import wait_for_wake_word
        from core.config import config
        with patch.object(config, "VOICE_AUTH_ENABLED", False):
            with patch("voice.wake_listener.listen", return_value="hey ultron"):
                with patch("voice.speech_output.speak") as mock_speak:
                    res = wait_for_wake_word()
                    self.assertTrue(res)
                    mock_speak.assert_called_with("What can I do for you, Boss?")

    # =========================================================================
    # 2. TELUGU MODE SWITCHING & PIPER TELUGU TTS
    # =========================================================================

    def test_03_telugu_language_mode_switch(self) -> None:
        """Verify 'speak in telugu' switches session.preferred_language to 'te'."""
        self.assertEqual(session.preferred_language, "en")
        res = orchestrator.process_command("speak in telugu")
        self.assertEqual(session.preferred_language, "te")
        self.assertIn("మాట్లాడగలను", res)

    def test_04_english_language_mode_switch(self) -> None:
        """Verify 'speak in english' switches session.preferred_language to 'en'."""
        session.preferred_language = "te"
        res = orchestrator.process_command("speak in english")
        self.assertEqual(session.preferred_language, "en")
        self.assertIn("English", res)

    def test_05_piper_telugu_model_loaded(self) -> None:
        """Verify local Piper ONNX te_IN-venkatesh-medium model loads cleanly."""
        voice = _get_piper_telugu_voice()
        self.assertIsNotNone(voice, "Piper ONNX te_IN-venkatesh-medium Telugu model should be loaded")

    def test_06_piper_telugu_tts_synthesis(self) -> None:
        """Verify speak() synthesizes real audio with Piper Telugu male voice."""
        res = speak("నేను తెలుగులో మాట్లాడగలను.", language="te")
        self.assertTrue(res, "Telugu TTS playback should complete cleanly")

    # =========================================================================
    # 3. DETERMINISTIC STORAGE DRIVE SAFETY (ZERO OLLAMA HALLUCINATION)
    # =========================================================================

    def test_07_d_drive_query_routes_to_system_control(self) -> None:
        """Verify 'tell about d drive' routes to get_disk_info and NOT Ollama."""
        res = orchestrator.process_command("tell about d drive")
        self.assertIn("storage details for drive d", res.lower())
        self.assertNotIn("hp victus", res.lower())
        self.assertNotIn("ollama", res.lower())

    def test_08_get_disk_info_dynamic_detection(self) -> None:
        """Verify get_disk_info dynamically queries D: drive and returns verified space."""
        info = system_control.get_disk_info("D")
        self.assertIn("drive d", info.lower())
        self.assertIn("total space", info.lower())
        self.assertNotIn("hp victus", info.lower())

    def test_09_non_existent_drive_returns_unavailable(self) -> None:
        """Verify requesting non-existent drive returns clean non-present message."""
        info = system_control.get_disk_info("Z")
        self.assertIn("not present", info.lower())

    def test_10_system_agent_disk_info_dispatch(self) -> None:
        """Verify SystemAgent handles disk_info action cleanly."""
        agent = SystemAgent()
        agent.initialize()
        res = agent.execute_task("t_disk", {"action": "disk_info", "drive": "C"})
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("drive c", str(res["result"]).lower())


if __name__ == "__main__":
    unittest.main()
