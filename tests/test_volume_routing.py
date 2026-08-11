import unittest
from unittest.mock import MagicMock, patch
from brain.orchestrator import orchestrator
from core.config import config
from core.session import session


class TestVolumeRouting(unittest.TestCase):

    def setUp(self):
        config.VOICE_AUTH_ENABLED = False
        session.reset()
        session.session_data.clear()
        session.preferred_language = "en"
        session.set_auth(True)
        session.enter_active()

    def test_volume_routing_with_prefixes(self):
        test_cases = [
            ("volume up", "Volume is now"),
            ("ultron volume up", "Volume is now"),
            ("hey ultron volume up", "Volume is now"),
            ("increase volume", "Volume is now"),
            ("ultron increase volume", "Volume is now"),
            ("volume down", "Volume is now"),
            ("ultron volume down", "Volume is now"),
            ("volume penchu", "Volume is now"),
            ("ultron volume penchu", "Volume is now"),
            ("volume tagginchu", "Volume is now"),
        ]

        for cmd, expected_substring in test_cases:
            with self.subTest(command=cmd):
                res = orchestrator.process_command(cmd)
                self.assertIn(
                    expected_substring,
                    res,
                    f"Command '{cmd}' failed to route deterministically. Got response: '{res}'"
                )

    def test_unrelated_commands_unchanged(self):
        # Verify unrelated commands route correctly without interference
        res = orchestrator.process_command("open brave")
        self.assertTrue(any(phrase in res.lower() for phrase in ["browser", "website", "ready"]), f"Unexpected response: {res}")


if __name__ == "__main__":
    unittest.main()
