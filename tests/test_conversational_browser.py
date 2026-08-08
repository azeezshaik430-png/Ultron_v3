import pytest
import time
from brain.orchestrator import orchestrator
from core.session import session

class TestConversationalBrowser:
    
    @pytest.fixture(autouse=True)
    def setup_orchestrator(self):
        self.orchestrator = orchestrator
        session.reset()
        session.session_data.clear()
        session.preferred_language = "en"
        yield
        session.reset()
        session.session_data.clear()

    def test_open_brave_flow_english(self):
        # 1. Ask to open brave
        res1 = self.orchestrator.process_command("open brave")
        assert "What website would you like me to open" in res1
        assert session.session_data.get("browser_state") == "WAITING_FOR_WEBSITE"
        
        # 2. Respond with YouTube
        res2 = self.orchestrator.process_command("youtube")
        assert "What would you like me to search for on Youtube, Boss?" in res2
        assert session.session_data.get("browser_state") == "WAITING_FOR_SEARCH_QUERY"
        assert session.session_data.get("browser_target") == "youtube"
        
        # 3. Respond with query
        res3 = self.orchestrator.process_command("ai agent tutorials")
        assert "Searching for ai agent tutorials on Youtube, Boss." in res3
        assert session.session_data.get("browser_state") is None

    def test_open_brave_flow_telugu(self):
        session.preferred_language = "te"
        
        res1 = self.orchestrator.process_command("brave open cheyyi")
        assert "ఏ website open చేయాలి Boss?" in res1
        assert session.session_data.get("browser_state") == "WAITING_FOR_WEBSITE"
        
        res2 = self.orchestrator.process_command("youtube")
        assert "Youtube లో ఏం search చేయాలి Boss?" in res2
        assert session.session_data.get("browser_state") == "WAITING_FOR_SEARCH_QUERY"
        
        res3 = self.orchestrator.process_command("jarvis ai")
        assert "వెతుకుతున్నాను బాస్." in res3
        assert session.session_data.get("browser_state") is None

    def test_cancel_flow(self):
        res1 = self.orchestrator.process_command("open brave")
        assert session.session_data.get("browser_state") == "WAITING_FOR_WEBSITE"
        
        res2 = self.orchestrator.process_command("cancel")
        assert "Cancelled, Boss." in res2
        assert session.session_data.get("browser_state") is None
        
    def test_invalid_website_flow(self):
        res1 = self.orchestrator.process_command("open brave")
        assert session.session_data.get("browser_state") == "WAITING_FOR_WEBSITE"
        
        res2 = self.orchestrator.process_command("randominvalidwebsite")
        assert "I don't recognize that website. Navigation cancelled." in res2
        assert session.session_data.get("browser_state") is None

    def test_one_shot_english(self):
        res1 = self.orchestrator.process_command("open youtube and search ai agents")
        # Ensure state was bypassed and it just executed
        assert session.session_data.get("browser_state") is None
        assert "is open, Boss" in res1

    def test_one_shot_telugu(self):
        session.preferred_language = "te"
        res1 = self.orchestrator.process_command("youtube lo ai agents search cheyyi")
        assert session.session_data.get("browser_state") is None
        assert "ఓపెన్ చేశాను, Boss" in res1

    def test_explicit_override(self):
        res1 = self.orchestrator.process_command("open brave")
        assert session.session_data.get("browser_state") == "WAITING_FOR_WEBSITE"
        
        res2 = self.orchestrator.process_command("open whatsapp")
        # Should override and open whatsapp
        assert session.session_data.get("browser_state") is None
        assert "WhatsApp Web is open" in res2 or "Whatsapp is open" in res2

    def test_explicit_override_search(self):
        res1 = self.orchestrator.process_command("open brave")
        res2 = self.orchestrator.process_command("youtube")
        assert session.session_data.get("browser_state") == "WAITING_FOR_SEARCH_QUERY"
        
        res3 = self.orchestrator.process_command("close youtube")
        # Should close browser
        assert session.session_data.get("browser_state") is None
        assert "browser has been closed" in res3.lower()
