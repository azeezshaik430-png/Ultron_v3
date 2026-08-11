import unittest
import time
from brain.orchestrator import orchestrator
from core.session import session

class TestConversationalBrowser(unittest.TestCase):

    def setUp(self):
        self.orchestrator = orchestrator
        session.reset()
        session.session_data.clear()
        session.preferred_language = "en"

    def tearDown(self):
        session.reset()
        session.session_data.clear()

    def test_open_brave_flow_english(self):
        res1 = self.orchestrator.process_command("open brave")
        self.assertTrue(isinstance(res1, str) and len(res1) > 0)
        
    def test_open_brave_flow_telugu(self):
        session.preferred_language = "te"
        res1 = self.orchestrator.process_command("brave open cheyyi")
        self.assertTrue(isinstance(res1, str) and len(res1) > 0)

    def test_cancel_flow(self):
        res1 = self.orchestrator.process_command("open brave")
        res2 = self.orchestrator.process_command("cancel")
        self.assertTrue(isinstance(res2, str))
        
    def test_invalid_website_flow(self):
        res1 = self.orchestrator.process_command("open brave")
        self.assertTrue(isinstance(res1, str))

    def test_one_shot_english(self):
        res1 = self.orchestrator.process_command("open youtube and search ai agents")
        self.assertTrue(isinstance(res1, str))

    def test_one_shot_telugu(self):
        session.preferred_language = "te"
        res1 = self.orchestrator.process_command("youtube lo ai agents search cheyyi")
        self.assertTrue(isinstance(res1, str))

    def test_explicit_override(self):
        res1 = self.orchestrator.process_command("open brave")
        res2 = self.orchestrator.process_command("open whatsapp")
        self.assertTrue(isinstance(res2, str))

    def test_explicit_override_search(self):
        res1 = self.orchestrator.process_command("open brave")
        res2 = self.orchestrator.process_command("youtube")
        res3 = self.orchestrator.process_command("close youtube")
        self.assertTrue(isinstance(res3, str))


if __name__ == "__main__":
    unittest.main()
