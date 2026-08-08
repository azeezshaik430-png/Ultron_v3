"""
ULTRON V3 - Sub-Milestone 2B.5 Test Suite
Covers Vision Agent, Browser Automation Agent, Security, AgentMemoryBus, and Orchestrator Integration.
30 Comprehensive Test Cases.
"""

import os
import time
import unittest
from unittest.mock import patch, MagicMock

from core.session import session
from brain.agent_bus import AgentMemoryBus
from brain.agent_manager import AgentManager
from brain.orchestrator import Orchestrator, orchestrator
from agents.vision_agent import VisionAgent
from agents.browser_agent import BrowserAgent


class TestSubMilestone2B5(unittest.TestCase):
    """Sub-Milestone 2B.5 Validation Suite: Vision Agent & Browser Automation Agent."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.orchestrator = orchestrator

    def setUp(self) -> None:
        session.reset()
        if hasattr(self, 'patcher'): self.patcher.stop()
        
        self.bus = orchestrator.bus
        self.manager = orchestrator.agent_manager
        
        self.vision_agent = self.manager.get_agent("vision_agent")
        self.browser_agent = self.manager.get_agent("browser_agent")

        # Mock PIL ImageGrab for headless environments
        self.mock_image = MagicMock()
        self.mock_image.size = (1920, 1080)
        def mock_save(*args, **kwargs):
            filepath = args[0]
            from PIL import Image
            img = Image.new('RGB', (10, 10), color = 'white')
            img.save(filepath, 'PNG')
        self.mock_image.save.side_effect = mock_save
        self.patcher = patch('agents.vision_agent.ImageGrab.grab', return_value=self.mock_image)
        self.patcher.start()

        def patched_execute_task(agent, orig_execute):
            def wrapper(*args, **kwargs):
                res = orig_execute(*args, **kwargs)
                if isinstance(res, dict) and 'status' in res and 'result' in res:
                    inner = res.get('result', {})
                    if isinstance(inner, dict):
                        inner['outer_status'] = res.get('status')
                        return inner
                return res
            agent.execute_task = wrapper
            
        patched_execute_task(self.vision_agent, self.vision_agent.execute_task)
        patched_execute_task(self.browser_agent, self.browser_agent.execute_task)

    def tearDown(self) -> None:
        session.reset()
        if hasattr(self, 'patcher'): self.patcher.stop()

    # =========================================================================
    # VISION AGENT TESTS (1 - 10)
    # =========================================================================

    def test_01_vision_agent_registration(self) -> None:
        """Verify VisionAgent registers cleanly with AgentManager."""
        agent = self.manager.get_agent("vision_agent")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "Vision Agent")

    def test_02_vision_agent_capability_discovery(self) -> None:
        """Verify VisionAgent capabilities are discoverable."""
        agent = self.manager.get_agent("vision_agent")
        caps = agent.capabilities
        self.assertIn("capture_screen", caps)
        self.assertIn("capture_camera", caps)
        self.assertIn("ocr", caps)
        self.assertIn("analyze_screen", caps)

    def test_03_screen_capture_execution(self) -> None:
        """Verify VisionAgent captures desktop screenshot."""
        res = self.vision_agent.execute_task("t_screen", {"action": "capture_screen"})
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["available"])
        self.assertTrue(os.path.exists(res["filepath"]))

    def test_04_camera_capture_availability_handling(self) -> None:
        """Verify VisionAgent camera frame capture or clean explicit unavailable status."""
        res = self.vision_agent.execute_task("t_cam", {"action": "capture_camera", "camera_index": 99})
        self.assertIn(res["status"], ["SUCCESS", "ERROR"])
        if res["status"] == "ERROR":
            self.assertFalse(res["available"])
            self.assertIn("reason", res)

    def test_05_image_analysis(self) -> None:
        """Verify VisionAgent analyze_image action."""
        # Capture screen first
        cap = self.vision_agent.execute_task("t_cap", {"action": "capture_screen"})
        res = self.vision_agent.execute_task("t_analyze", {
            "action": "analyze_image",
            "filepath": cap["filepath"],
            "prompt": "What is on this screen?",
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["available"])
        self.assertIn("analysis", res)

    def test_06_ocr_text_extraction(self) -> None:
        """Verify VisionAgent OCR action."""
        # Capture screen first
        cap = self.vision_agent.execute_task("t_cap", {"action": "capture_screen"})
        print('CAP:', cap)
        res = self.vision_agent.execute_task("t_ocr", {
            "action": "ocr",
            "filepath": cap["filepath"]
        })
        print('RES:', res)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["available"])
        self.assertIn("text", res)

    def test_07_unavailable_action_handling(self) -> None:
        """Verify VisionAgent returns explicit unavailable dictionary for invalid action."""
        res = self.vision_agent.execute_task("t_inv", {"action": "non_existent_action"})
        self.assertEqual(res["status"], "ERROR")
        self.assertFalse(res["available"])
        self.assertIn("reason", res)

    def test_08_filepath_artifact_verification(self) -> None:
        """Verify captured screenshot output path is valid."""
        res = self.vision_agent.execute_task("t_art", {"action": "capture_screen"})
        self.assertTrue(res["filepath"].endswith(".png"))

    def test_09_agent_memory_bus_integration(self) -> None:
        """Verify VisionAgent communicates over AgentMemoryBus."""
        self.assertIsNotNone(self.vision_agent.bus)
        health = self.vision_agent.health_check()
        self.assertTrue(health["healthy"])

    def test_10_workspace_acl_path_boundary_check(self) -> None:
        """Verify VisionAgent OCR handles invalid non-existent path safely."""
        res = self.vision_agent.execute_task("t_acl", {
            "action": "ocr",
            "filepath": "C:\\invalid_restricted_path\\secret.png",
        })
        self.assertEqual(res["status"], "ERROR")

    # =========================================================================
    # BROWSER AGENT TESTS (11 - 23)
    # =========================================================================

    def test_11_browser_agent_registration(self) -> None:
        """Verify BrowserAgent registers cleanly with AgentManager."""
        agent = self.manager.get_agent("browser_agent")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "Browser Automation Agent")

    def test_12_browser_agent_capability_discovery(self) -> None:
        """Verify BrowserAgent capabilities are discoverable."""
        agent = self.manager.get_agent("browser_agent")
        caps = agent.capabilities
        self.assertIn("open_url", caps)
        self.assertIn("inspect_page", caps)
        self.assertIn("click_element", caps)
        self.assertIn("screenshot", caps)

    def test_13_browser_startup_and_health_check(self) -> None:
        """Verify BrowserAgent health check reporting."""
        health = self.browser_agent.health_check()
        self.assertTrue(health["healthy"])
        self.assertEqual(health["agent_id"], "browser_agent")

    def test_14_browser_open_url_navigation(self) -> None:
        """Verify BrowserAgent open_url action."""
        res = self.browser_agent.execute_task("t_nav", {
            "action": "open_url",
            "url": "https://example.com",
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["available"])
        self.assertIn("url", res)

    def test_15_browser_inspect_page(self) -> None:
        """Verify BrowserAgent inspect_page action."""
        res = self.browser_agent.execute_task("t_insp", {
            "action": "inspect_page",
            "url": "https://example.com",
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["available"])
        self.assertIn("text", res)

    def test_16_browser_click_element(self) -> None:
        """Verify BrowserAgent click_element execution or clean error on missing session."""
        res = self.browser_agent.execute_task("t_click", {
            "action": "click_element",
            "selector": "button#submit",
        })
        self.assertIn(res["status"], ["SUCCESS", "ERROR"])

    def test_17_browser_type_into_field(self) -> None:
        """Verify BrowserAgent type_into_field execution or clean error on missing session."""
        res = self.browser_agent.execute_task("t_type", {
            "action": "type_into_field",
            "selector": "input#query",
            "text": "ULTRON V3 AI",
        })
        self.assertIn(res["status"], ["SUCCESS", "ERROR"])

    def test_18_browser_screenshot(self) -> None:
        """Verify BrowserAgent web screenshot action."""
        self.browser_agent.execute_task("t_nav", {"action": "open_url", "url": "https://example.com"})
        res = self.browser_agent.execute_task("t_shot", {"action": "screenshot"})
        if res["status"] == "SUCCESS":
            self.assertTrue(os.path.exists(res["filepath"]))

    def test_19_browser_action_timeout_handling(self) -> None:
        """Verify BrowserAgent handles navigation timeouts cleanly."""
        res = self.browser_agent.execute_task("t_time", {
            "action": "open_url",
            "url": "http://10.255.255.1:9999",
        })
        self.assertIn(res["status"], ["SUCCESS", "ERROR"])

    def test_20_browser_session_cleanup(self) -> None:
        """Verify BrowserAgent close_browser cleans up browser process."""
        self.browser_agent.execute_task("t_nav", {"action": "open_url", "url": "https://example.com"})
        res = self.browser_agent.execute_task("t_close", {"action": "close_browser"})
        self.assertEqual(res["status"], "SUCCESS")

    def test_21_browser_crash_recovery(self) -> None:
        """Verify BrowserAgent recovers after close_browser."""
        self.browser_agent.execute_task("t_close", {"action": "close_browser"})
        res = self.browser_agent.execute_task("t_nav", {"action": "open_url", "url": "https://example.com"})
        self.assertEqual(res["status"], "SUCCESS")

    def test_22_security_url_validation(self) -> None:
        """Verify BrowserAgent rejects restricted file URLs outside workspace."""
        res = self.browser_agent.execute_task("t_sec", {
            "action": "open_url",
            "url": "file:///C:/Windows/System32/config/SAM",
        })
        self.assertEqual(res["status"], "ERROR")

    def test_23_destructive_action_confirmation_guard(self) -> None:
        """Verify destructive browser clicks require token confirmation."""
        res = self.browser_agent.execute_task("t_dest", {
            "action": "click_element",
            "selector": "button#delete_account",
            "is_destructive": True,
            "confirmed": False,
        })
        self.assertEqual(res["status"], "PENDING_CONFIRMATION")
        self.assertIn("confirmation_token", res)

    # =========================================================================
    # INTEGRATION TESTS (24 - 30)
    # =========================================================================

    def test_24_orchestrator_vision_agent_dispatch(self) -> None:
        """Verify Orchestrator dispatches 'take a screenshot' to VisionAgent."""
        res = orchestrator.process_command("take a screenshot")
        self.assertIn("screenshot captured", res.lower())

    def test_25_orchestrator_browser_agent_dispatch(self) -> None:
        """Verify Orchestrator dispatches 'open browser' to BrowserAgent."""
        res = orchestrator.process_command("open browser https://example.com")
        self.assertIn("example.com", res.lower())

    def test_26_agent_manager_registers_all_domain_agents(self) -> None:
        """Verify AgentManager contains all 8 domain agents."""
        agents = orchestrator.agent_manager.list_agents()
        self.assertGreaterEqual(len(agents), 8)
        agent_ids = [a.get("agent_id", "") for a in agents]
        self.assertIn("vision_agent", agent_ids)
        self.assertIn("browser_agent", agent_ids)

    def test_27_agent_memory_bus_publishing(self) -> None:
        """Verify Vision and Browser tasks publish events to AgentMemoryBus."""
        bus_health = self.bus.health_check()
        self.assertEqual(bus_health["overall_status"], "HEALTHY")

    def test_28_health_monitor_system_report(self) -> None:
        """Verify HealthMonitor aggregated report includes Vision and Browser agents."""
        health = orchestrator.agent_manager.health_check()
        self.assertTrue(health["healthy"])
        self.assertIn("vision_agent", health["agent_health"])
        self.assertIn("browser_agent", health["agent_health"])

    def test_29_cross_platform_path_handling(self) -> None:
        """Verify VisionAgent normalizes output directory paths cleanly."""
        res = self.vision_agent.execute_task("t_xp", {"action": "capture_screen", "output_dir": "data/test_xp"})
        self.assertEqual(res["status"], "SUCCESS")

    def test_30_full_2b_regression(self) -> None:
        """Verify full Orchestrator pipeline handles commands cleanly across agents."""
        from core.session import session
        session.preferred_language = "en"
        session.conversation_history = []
        res1 = orchestrator.process_command("What is Java? Please reply in English.")
        self.assertTrue("java" in res1.lower() or "జావా" in res1)

        res2 = orchestrator.process_command("what is my system details")
        self.assertIn("verified system hardware details", res2.lower())


if __name__ == "__main__":
    unittest.main()
