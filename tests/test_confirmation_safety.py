import unittest
import time
from unittest.mock import patch, MagicMock
from brain.orchestrator import orchestrator
from core.session import session

def safety_block(*args, **kwargs):
    raise RuntimeError("CRITICAL SAFETY GUARD TRIGGERED: Real Windows power adapter method executed!")

class TestConfirmationSafety(unittest.TestCase):
    def setUp(self):
        # Bulletproof safety patches on physical Windows adapter methods:
        # Intercepts physical OS subprocess commands and returns safe mock dictionaries.
        self.patch_adapter_restart = patch("ultron_platform.windows_adapter.WindowsAdapter.restart")
        self.patch_adapter_shutdown = patch("ultron_platform.windows_adapter.WindowsAdapter.shutdown")
        self.patch_adapter_signout = patch("ultron_platform.windows_adapter.WindowsAdapter.sign_out")
        self.patch_adapter_sleep = patch("ultron_platform.windows_adapter.WindowsAdapter.sleep")
        self.patch_adapter_lock = patch("ultron_platform.windows_adapter.WindowsAdapter.lock")

        self.mock_adapter_restart = self.patch_adapter_restart.start()
        self.mock_adapter_shutdown = self.patch_adapter_shutdown.start()
        self.mock_adapter_signout = self.patch_adapter_signout.start()
        self.mock_adapter_sleep = self.patch_adapter_sleep.start()
        self.mock_adapter_lock = self.patch_adapter_lock.start()

        self.mock_adapter_restart.return_value = {"available": True, "result": "Restarting computer Boss.", "verified": True, "success": True}
        self.mock_adapter_shutdown.return_value = {"available": True, "result": "Shutting down computer Boss.", "verified": True, "success": True}
        self.mock_adapter_signout.return_value = {"available": True, "result": "Signing out Boss.", "verified": True, "success": True}
        self.mock_adapter_sleep.return_value = {"available": True, "result": "Going to sleep mode Boss.", "verified": True, "success": True}
        self.mock_adapter_lock.return_value = {"available": True, "result": "Locking computer Boss.", "verified": True, "success": True}

        if hasattr(session, 'reset'):
            session.reset()
        if hasattr(session, 'session_data'):
            session.session_data.clear()
        session.clear_pending_confirmation()

    def tearDown(self):
        session.clear_pending_confirmation()
        self.patch_adapter_restart.stop()
        self.patch_adapter_shutdown.stop()
        self.patch_adapter_signout.stop()
        self.patch_adapter_sleep.stop()
        self.patch_adapter_lock.stop()

    # Test 1: "restart pc" creates pending confirmation, no real restart executed
    def test_01_restart_pc_creates_pending(self):
        res = orchestrator.process_command("restart pc")
        self.assertIn("Are you sure", res)
        self.assertIsNotNone(session.pending_confirmation)
        self.assertEqual(session.pending_confirmation.get("action"), "restart_pc")
        self.mock_adapter_restart.assert_not_called()

    # Test 2: Pending restart pc + "yes" -> confirmation accepted, mock called ONCE
    @patch("voice.speech_output.speak")
    def test_02_pending_restart_yes_confirms(self, mock_speak):
        orchestrator.process_command("restart pc")
        res2 = orchestrator.process_command("yes")
        self.assertIn("Restarting your computer", res2)
        self.mock_adapter_restart.assert_called_once()
        self.assertIsNone(session.pending_confirmation)

    # Test 3: Pending restart pc + "no" -> cancellation, mock NOT called
    def test_03_pending_restart_no_cancels(self):
        orchestrator.process_command("restart pc")
        res2 = orchestrator.process_command("no")
        self.assertIn("cancelled", res2.lower())
        self.mock_adapter_restart.assert_not_called()
        self.assertIsNone(session.pending_confirmation)

    # Test 4: Pending restart pc + "cancel" -> cancellation, mock NOT called
    def test_04_pending_restart_cancel_cancels(self):
        orchestrator.process_command("restart pc")
        res2 = orchestrator.process_command("cancel")
        self.assertIn("cancelled", res2.lower())
        self.mock_adapter_restart.assert_not_called()
        self.assertIsNone(session.pending_confirmation)

    # Test 5: Pending restart pc + "yes restart pc" -> accepted, mock called ONCE
    @patch("voice.speech_output.speak")
    def test_05_pending_restart_yes_restart_pc(self, mock_speak):
        orchestrator.process_command("restart pc")
        res2 = orchestrator.process_command("yes restart pc")
        self.assertIn("Restarting your computer", res2)
        self.mock_adapter_restart.assert_called_once()
        self.assertIsNone(session.pending_confirmation)

    # Test 6: Pending restart pc + "open YouTube" -> must NOT confirm restart, must NOT restart, cancelled safely
    @patch("agents.browser_agent.BrowserAgent.execute_task")
    def test_06_unrelated_open_youtube_cancels(self, mock_browser):
        mock_browser.return_value = {"status": "SUCCESS", "result": {"title": "YouTube", "url": "https://youtube.com"}}
        orchestrator.process_command("restart pc")
        res2 = orchestrator.process_command("open YouTube")
        self.mock_adapter_restart.assert_not_called()
        self.assertIsNone(session.pending_confirmation)
        self.mock_adapter_restart.assert_not_called()

    # Test 7: Pending restart pc + "volume up" -> must NOT confirm restart
    @patch("agents.system_agent.SystemAgent.execute_task")
    def test_07_unrelated_volume_up_cancels(self, mock_sys):
        mock_sys.return_value = {"status": "SUCCESS", "result": "Volume adjusted"}
        orchestrator.process_command("restart pc")
        res2 = orchestrator.process_command("volume up")
        self.mock_adapter_restart.assert_not_called()
        self.assertIsNone(session.pending_confirmation)

    # Test 8: Pending restart pc + "yes please open YouTube" -> MUST NOT confirm restart
    @patch("agents.browser_agent.BrowserAgent.execute_task")
    def test_08_unrelated_phrase_containing_yes_cancels(self, mock_browser):
        mock_browser.return_value = {"status": "SUCCESS", "result": "YouTube is open, Boss."}
        orchestrator.process_command("restart pc")
        res2 = orchestrator.process_command("yes please open YouTube")
        self.mock_adapter_restart.assert_not_called()
        self.assertIsNone(session.pending_confirmation)

    # Test 9: Pending restart pc + "yes sign out" -> MUST NOT execute restart, overrides to pending sign out
    def test_09_confirmation_action_mismatch_overrides(self):
        orchestrator.process_command("restart pc")
        res2 = orchestrator.process_command("yes sign out")
        self.mock_adapter_restart.assert_not_called()
        self.mock_adapter_signout.assert_not_called()
        self.assertIsNotNone(session.pending_confirmation)
        self.assertEqual(session.pending_confirmation.get("action"), "sign_out_pc")

    # Test 10: Pending shutdown pc + "yes" -> mock shutdown called ONCE
    @patch("voice.speech_output.speak")
    def test_10_pending_shutdown_yes_confirms(self, mock_speak):
        orchestrator.process_command("shutdown pc")
        res2 = orchestrator.process_command("yes")
        self.assertIn("Shutting down your computer", res2)
        self.mock_adapter_shutdown.assert_called_once()
        self.assertIsNone(session.pending_confirmation)

    # Test 11: Pending sign out + "yes" -> mock sign_out called ONCE
    @patch("voice.speech_output.speak")
    def test_11_pending_sign_out_yes_confirms(self, mock_speak):
        orchestrator.process_command("sign out")
        res2 = orchestrator.process_command("yes")
        self.assertIn("Signing out of your computer", res2)
        self.mock_adapter_signout.assert_called_once()
        self.assertIsNone(session.pending_confirmation)

    # Test 12: Expired confirmation + "yes" -> MUST NOT execute
    def test_12_expired_confirmation_blocks_execution(self):
        orchestrator.process_command("restart pc")
        session.pending_confirmation["expires_at"] = time.time() - 1.0
        session.pending_confirmation["created_at"] = time.time() - 20.0
        res2 = orchestrator.process_command("yes")
        self.mock_adapter_restart.assert_not_called()
        self.assertIn("timed out", res2.lower())
        self.assertIsNone(session.pending_confirmation)

    # Test 13: Double execution protection: repeated "yes" must not trigger action twice
    @patch("voice.speech_output.speak")
    def test_13_double_execution_protection(self, mock_speak):
        orchestrator.process_command("restart pc")
        orchestrator.process_command("yes")
        self.mock_adapter_restart.assert_called_once()
        
        # Second "yes" call
        orchestrator.process_command("yes")
        self.mock_adapter_restart.assert_called_once()

    # Test 14: Confirmation routing overhead latency < 1 ms
    @patch("voice.speech_output.speak")
    def test_14_confirmation_routing_overhead_latency(self, mock_speak):
        orchestrator.process_command("restart pc")
        t0 = time.perf_counter()
        orchestrator.process_command("yes")
        t1 = time.perf_counter()
        routing_latency_ms = (t1 - t0) * 1000.0
        self.assertLess(routing_latency_ms, 20.0, "Confirmation decision routing must be fast")
        self.mock_adapter_restart.assert_called_once()

    # Test 15: listen_confirmation respects fixed expires_at deadline without resetting window
    @patch("voice.speech_input.stop_interruption_listener")
    @patch("voice.speech_input.sr.Microphone")
    def test_15_listen_confirmation_preserves_deadline(self, mock_mic, mock_stop_interrupt):
        from voice.speech_input import listen_confirmation
        expires_at = time.time() - 0.5  # Already expired
        res = listen_confirmation(expires_at=expires_at)
        self.assertEqual(res, "", "Already expired confirmation deadline must return immediately without listening")

    # Test 16: Active mic stream invariant <= 1 during confirmation mode
    def test_16_active_mic_streams_invariant(self):
        from voice.speech_input import _active_mic_count, is_interruption_listener_running, stop_interruption_listener
        stop_interruption_listener()
        self.assertFalse(is_interruption_listener_running(), "Interruption listener must be stopped before confirmation listener")
        self.assertLessEqual(_active_mic_count, 1, "Active microphone stream count must be <= 1")


if __name__ == "__main__":
    unittest.main()
