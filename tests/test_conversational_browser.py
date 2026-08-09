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
        # 1. Ask to open brave
        res1 = self.orchestrator.process_command("open brave")
        self.assertIn("What website would you like me to open", res1)
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_WEBSITE")
        
        # 2. Respond with YouTube
        res2 = self.orchestrator.process_command("youtube")
        self.assertIn("What would you like me to search for on Youtube, Boss?", res2)
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_SEARCH_QUERY")
        self.assertEqual(session.session_data.get("browser_target"), "youtube")
        
        # 3. Respond with query
        res3 = self.orchestrator.process_command("ai agent tutorials")
        self.assertIn("Searching for ai agent tutorials on Youtube, Boss.", res3)
        self.assertIsNone(session.session_data.get("browser_state"))

    def test_open_brave_flow_telugu(self):
        session.preferred_language = "te"
        
        res1 = self.orchestrator.process_command("brave open cheyyi")
        self.assertIn("ఏ website open చేయాలి Boss?", res1)
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_WEBSITE")
        
        res2 = self.orchestrator.process_command("youtube")
        self.assertIn("Youtube లో ఏం search చేయాలి Boss?", res2)
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_SEARCH_QUERY")
        
        res3 = self.orchestrator.process_command("jarvis ai")
        self.assertIn("వెతుకుతున్నాను బాస్.", res3)
        self.assertIsNone(session.session_data.get("browser_state"))

    def test_cancel_flow(self):
        res1 = self.orchestrator.process_command("open brave")
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_WEBSITE")
        
        res2 = self.orchestrator.process_command("cancel")
        self.assertIn("Cancelled, Boss.", res2)
        self.assertIsNone(session.session_data.get("browser_state"))
        
    def test_invalid_website_flow(self):
        res1 = self.orchestrator.process_command("open brave")
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_WEBSITE")
        
        res2 = self.orchestrator.process_command("randominvalidwebsite")
        self.assertIn("I don't recognize that website. Navigation cancelled.", res2)
        self.assertIsNone(session.session_data.get("browser_state"))

    def test_one_shot_english(self):
        res1 = self.orchestrator.process_command("open youtube and search ai agents")
        self.assertIsNone(session.session_data.get("browser_state"))
        self.assertIn("is open, Boss", res1)

    def test_one_shot_telugu(self):
        session.preferred_language = "te"
        res1 = self.orchestrator.process_command("youtube lo ai agents search cheyyi")
        self.assertIsNone(session.session_data.get("browser_state"))
        self.assertIn("ఓపెన్ చేశాను, Boss", res1)

    def test_explicit_override(self):
        res1 = self.orchestrator.process_command("open brave")
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_WEBSITE")
        
        res2 = self.orchestrator.process_command("open whatsapp")
        self.assertIsNone(session.session_data.get("browser_state"))
        self.assertTrue("WhatsApp Web is open" in res2 or "Whatsapp is open" in res2)

    def test_explicit_override_search(self):
        res1 = self.orchestrator.process_command("open brave")
        res2 = self.orchestrator.process_command("youtube")
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_SEARCH_QUERY")
        
        res3 = self.orchestrator.process_command("close youtube")
        self.assertIsNone(session.session_data.get("browser_state"))
        self.assertIn("browser has been closed", res3.lower())


if __name__ == "__main__":
    unittest.main()
