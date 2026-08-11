"""
ULTRON V3 - Wake Word & Combined Command Extraction Unit Test Suite
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from voice.wake_word import check_wake_word, extract_wake_word_and_command


class TestWakeWordUnit(unittest.TestCase):
    """Unit tests for wake_word.py matching and extraction."""

    def test_01_wake_word_variations(self):
        """Test 1: Verify wake word variations match correctly."""
        self.assertTrue(check_wake_word("Hey Ultron"))
        self.assertTrue(check_wake_word("Ultron"))
        self.assertTrue(check_wake_word("Hey Altron"))
        self.assertTrue(check_wake_word("you wake up alpron"))

    def test_02_combined_command_extraction(self):
        """Test 2: Verify combined wake word and command extraction."""
        has_wake, cmd = extract_wake_word_and_command("Hey Ultron volume up")
        self.assertTrue(has_wake)
        self.assertEqual(cmd, "volume up")

        has_wake, cmd = extract_wake_word_and_command("Ultron volume down")
        self.assertTrue(has_wake)
        self.assertEqual(cmd, "volume down")

        has_wake, cmd = extract_wake_word_and_command("Hey Ultron open YouTube")
        self.assertTrue(has_wake)
        self.assertEqual(cmd, "open youtube")

    def test_03_unrelated_speech_rejection(self):
        """Test 3: Verify unrelated speech does not trigger wake word."""
        self.assertFalse(check_wake_word("Hey, how are you?"))
        self.assertFalse(check_wake_word("Open the browser"))
        self.assertFalse(check_wake_word("Volume up"))


if __name__ == "__main__":
    unittest.main()
