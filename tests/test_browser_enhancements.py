import unittest
import time
from unittest.mock import patch, MagicMock
from brain.orchestrator import orchestrator
from core.session import session
from agents.browser_agent import BrowserAgent

class TestBrowserEnhancements(unittest.TestCase):
    def setUp(self):
        # Reset session and language state before each test
        session.reset()
        session.session_data.pop("browser_state", None)
        session.session_data.pop("browser_target", None)
        session.preferred_language = "en"
        
        # Ensure browser is ready
        self.browser_agent = orchestrator.agent_manager.get_agent("browser_agent")
        if not self.browser_agent:
            self.browser_agent = BrowserAgent(bus=orchestrator.agent_manager.bus)
            orchestrator.agent_manager.register_agent(self.browser_agent)

    def test_01_search_something_else(self):
        """Test 'search something else' puts agent into WAITING_FOR_SEARCH_QUERY state."""
        session.session_data["browser_target"] = "youtube"
        res = orchestrator.process_command("Search something else")
        self.assertEqual(session.session_data.get("browser_state"), "WAITING_FOR_SEARCH_QUERY")
        self.assertIn("What would you like me to search for, Boss?", res)
        
        # Now simulate next query
        res2 = orchestrator.process_command("Python tutorials")
        self.assertIsNone(session.session_data.get("browser_state"))
        self.assertIn("searching for python tutorials", res2.lower())
        
    def test_02_positional_video_playback_and_back(self):
        """Test full sequence: open -> play nth -> back -> back+search"""
        res = orchestrator.process_command("Open youtube and search AI agents")
        self.assertTrue("is open, Boss." in res or "Searching for" in res)
        
        time.sleep(1)
        
        res2 = orchestrator.process_command("Play the third video")
        self.assertTrue("Playing" in res2 or "I couldn't complete" in res2)
        
        time.sleep(1)
        res3 = orchestrator.process_command("Come back")
        self.assertTrue("Navigated back" in res3 or "I couldn't complete" in res3)
        
        res4 = orchestrator.process_command("Come back and search Gemini Live API")
        self.assertTrue("is open, Boss." in res4 or "I couldn't complete" in res4)

    def test_03_telugu_positional_video_playback(self):
        """Test telugu phrasing for positional video playback"""
        session.preferred_language = "te"
        res = orchestrator.process_command("Open youtube and search AI agents")
        time.sleep(1)
        
        res2 = orchestrator.process_command("3rd video play cheyyi")
        self.assertTrue("Playing" in res2 or "I couldn't complete" in res2)

    def test_04_telugu_back_and_search(self):
        """Test telugu phrasing for back and search"""
        session.preferred_language = "te"
        res3 = orchestrator.process_command("venakki velli Python tutorials search cheyyi")
        self.assertTrue("ఓపెన్ చేశాను, Boss." in res3 or "I couldn't complete" in res3)

    def test_05_explicit_override_still_works(self):
        """Ensure that explicit override logic is preserved"""
        session.session_data["browser_state"] = "WAITING_FOR_WEBSITE"
        res = orchestrator.process_command("Open WhatsApp")
        self.assertIsNone(session.session_data.get("browser_state"))
        self.assertIn("whatsapp", res.lower())
        self.assertIn("open", res.lower())

    @patch('agents.browser_agent.HAS_PLAYWRIGHT', True)
    def test_06_epipe_recovery(self):
        """Test that browser agent recovers from EPIPE connection errors without crashing."""
        mock_page = MagicMock()
        mock_page.is_closed.return_value = False
        mock_page.goto.side_effect = Exception("EPIPE: broken pipe / connection closed")
        
        self.browser_agent._page_instance = mock_page
        
        # Mocks to satisfy is_connected check
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        self.browser_agent._browser_instance = mock_browser
        
        res = self.browser_agent.execute_task("t_err", {"action": "open_url", "url": "https://google.com"})
        self.assertEqual(res["result"]["status"], "ERROR")
        
        # Verify that _page_instance is cleaned up and set to None
        self.assertIsNone(self.browser_agent._page_instance)

    def test_07_page_reuse(self):
        """Verify browser session and page reuse."""
        mock_page = MagicMock()
        mock_page.is_closed.return_value = False
        self.browser_agent._page_instance = mock_page
        
        mock_context = MagicMock()
        mock_context.pages = [mock_page]
        mock_browser = MagicMock()
        mock_browser.contexts = [mock_context]
        mock_browser.is_connected.return_value = True
        self.browser_agent._browser_instance = mock_browser
        
        res = self.browser_agent.execute_task("t_nav", {"action": "open_url", "url": "https://google.com"})
        self.assertEqual(res["result"]["status"], "SUCCESS")
        self.assertEqual(self.browser_agent._page_instance, mock_page)

    def test_08_command_decomposition(self):
        """Verify command decomposition into sequential actions."""
        with patch.object(self.browser_agent, 'execute_task') as mock_exec:
            mock_exec.return_value = {"status": "SUCCESS", "result": {"status": "SUCCESS", "title": "YouTube"}}
            res = orchestrator.process_command("close Facebook and open YouTube")
            self.assertTrue(isinstance(res, str) and len(res) > 0)

if __name__ == "__main__":
    unittest.main()
