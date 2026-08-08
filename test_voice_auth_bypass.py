"""
ULTRON V3 - Voice Authentication Bypass Unit & Integration Test Suite
Verifies:
1. Default configuration keeps VOICE_AUTH_ENABLED = True.
2. Voice authentication enabled -> speaker verification is enforced.
3. Voice authentication disabled (VOICE_AUTH_ENABLED=False) -> dev bypass grants access cleanly.
4. VoiceGuard threshold and neural verification engine remain 100% intact.
"""

import os
import unittest
from unittest.mock import patch
from core.config import config, Config
from voice.voice_guard import verify_boss, THRESHOLD


class TestVoiceAuthBypass(unittest.TestCase):
    """Test suite for voice authentication dev bypass configuration."""

    def test_01_default_config_enables_voice_auth(self) -> None:
        """Verify default configuration maintains VOICE_AUTH_ENABLED = True for production safety."""
        test_cfg = Config()
        self.assertTrue(test_cfg.VOICE_AUTH_ENABLED)

    def test_02_production_threshold_intact(self) -> None:
        """Verify VoiceGuard production threshold is unchanged (0.68)."""
        self.assertEqual(THRESHOLD, 0.68)

    def test_03_dev_bypass_grants_access(self) -> None:
        """Verify setting VOICE_AUTH_ENABLED = False bypasses verification and returns True."""
        with patch.object(config, "VOICE_AUTH_ENABLED", False):
            result = verify_boss("fake_sample.wav")
            self.assertTrue(result)

    def test_04_enforced_when_enabled(self) -> None:
        """Verify setting VOICE_AUTH_ENABLED = True enforces normal verify_boss check."""
        with patch.object(config, "VOICE_AUTH_ENABLED", True):
            # Non-existent file should reject / fail cleanly when auth is enabled
            with patch("os.path.exists", return_value=False):
                with patch("voice.voice_auth.register_voice"):
                    result = verify_boss("non_existent_voice.wav")
                    self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
