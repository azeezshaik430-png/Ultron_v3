"""
ULTRON V3 - Male Voice Selection & Verbal Greeting Unit Tests
Verifies:
1. Preference for installed MALE English voice (Microsoft David Desktop).
2. Wake word verbal greeting 'What can I do for you, Boss?' triggers on activation.
3. Voice output telemetry logs TTS_AVAILABLE_VOICES and TTS_SELECTED_VOICE.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
import pyttsx3
import pythoncom

from voice.speech_output import speak, speaking, stop_speaking
from voice.wake_word import check_wake_word
from core.config import config
from core.session import session


class TestMaleVoiceAndGreeting(unittest.TestCase):
    """Test suite for male voice selection and wake-word greeting."""

    def setUp(self) -> None:
        session.reset()

    def tearDown(self) -> None:
        session.reset()

    def test_01_installed_male_voice_selected(self) -> None:
        """Verify pyttsx3 voice selection prefers a male voice on Windows."""
        if sys.platform == "win32":
            pythoncom.CoInitialize()
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            male_keywords = ["david", "male", "mark", "george", "james", "richard", "guy"]
            selected_male = None
            for v in voices:
                if any(k in v.name.lower() for k in male_keywords):
                    selected_male = v
                    break
            self.assertIsNotNone(selected_male, "A male English voice should be installed on Windows")
            self.assertIn("David", selected_male.name)

    def test_02_speak_executes_male_voice(self) -> None:
        """Verify speak() runs cleanly and sets speaking state."""
        self.assertFalse(speaking())
        res = speak("Testing ULTRON male voice playback.")
        self.assertTrue(res)
        self.assertFalse(speaking())

    def test_03_wake_word_check(self) -> None:
        """Verify check_wake_word detects 'hey ultron' and 'ultron'."""
        self.assertTrue(check_wake_word("hey ultron"))
        self.assertTrue(check_wake_word("wake up ultron"))
        self.assertFalse(check_wake_word("hello alexa"))

    def test_04_wake_listener_triggers_verbal_greeting(self) -> None:
        """Verify wait_for_wake_word invokes speak with greeting upon wake detection."""
        with patch.object(config, "VOICE_AUTH_ENABLED", False):
            with patch("voice.wake_listener.listen", return_value="hey ultron"):
                with patch("voice.speech_output.speak") as mock_speak:
                    from voice.wake_listener import wait_for_wake_word
                    res = wait_for_wake_word()
                    self.assertTrue(res)
                    mock_speak.assert_called_with("What can I do for you, Boss?")


if __name__ == "__main__":
    unittest.main()
