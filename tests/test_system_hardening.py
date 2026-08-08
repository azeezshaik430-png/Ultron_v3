import unittest
import time
from unittest.mock import patch, MagicMock
from brain.orchestrator import orchestrator
from core.session import session
from ultron_platform.windows_adapter import WindowsAdapter

class TestSystemHardening(unittest.TestCase):
    def setUp(self):
        session.reset()
        session.session_data.clear()

    # System Power Tests
    def test_shutdown_confirmation_flow(self):
        res = orchestrator.process_command("shutdown my pc")
        self.assertIn("Are you sure", res)
        self.assertEqual(session.pending_confirmation.get("action"), "shutdown_pc")
        
        with patch('skills.windows_control._adapter') as mock_adapter:
            mock_adapter.return_value.shutdown.return_value = {"available": True, "result": "Shutting down computer Boss.", "verified": True, "success": True}
            res2 = orchestrator.process_command("yes")
            self.assertIn("Shutting down", res2)
            self.assertIsNone(session.pending_confirmation)

    def test_shutdown_cancellation_flow(self):
        orchestrator.process_command("shutdown my pc")
        res = orchestrator.process_command("no")
        self.assertIn("cancelled", res.lower())
        self.assertIsNone(session.pending_confirmation)

    def test_restart_confirmation_flow(self):
        res = orchestrator.process_command("restart computer")
        self.assertIn("Are you sure", res)
        self.assertEqual(session.pending_confirmation.get("action"), "restart_pc")
        
        with patch('skills.windows_control._adapter') as mock_adapter:
            mock_adapter.return_value.restart.return_value = {"available": True, "result": "Restarting computer Boss.", "verified": True, "success": True}
            res2 = orchestrator.process_command("yes")
            self.assertIn("Restarting", res2)

    def test_sign_out_confirmation_flow(self):
        res = orchestrator.process_command("sign me out")
        self.assertIn("Are you sure", res)
        self.assertEqual(session.pending_confirmation.get("action"), "sign_out_pc")
        
        with patch('skills.windows_control._adapter') as mock_adapter:
            mock_adapter.return_value.sign_out.return_value = {"available": True, "result": "Signing out Boss.", "verified": True, "success": True}
            res2 = orchestrator.process_command("yes")
            self.assertIn("Signing out", res2)

    def test_lock_confirmation_flow(self):
        res = orchestrator.process_command("lock pc")
        self.assertIn("Are you sure", res)
        self.assertEqual(session.pending_confirmation.get("action"), "lock_pc")
        
        with patch('skills.windows_control._adapter') as mock_adapter:
            mock_adapter.return_value.lock.return_value = {"available": True, "result": "Locking computer Boss.", "verified": True, "success": True}
            res2 = orchestrator.process_command("yes")
            self.assertIn("Locking", res2)

    def test_sleep_confirmation_flow(self):
        res = orchestrator.process_command("sleep pc")
        self.assertIn("Are you sure", res)
        self.assertEqual(session.pending_confirmation.get("action"), "sleep_pc")
        
        with patch('skills.windows_control._adapter') as mock_adapter:
            mock_adapter.return_value.sleep.return_value = {"available": True, "result": "Going to sleep mode Boss.", "verified": True, "success": True}
            res2 = orchestrator.process_command("yes")
            self.assertIn("sleep", res2.lower())

    def test_confirmation_reset_on_unrelated_command(self):
        orchestrator.process_command("restart pc")
        self.assertIsNotNone(session.pending_confirmation)
        res = orchestrator.process_command("what is the time")
        self.assertIsNone(session.pending_confirmation)
        self.assertNotIn("Are you sure", res)

    # Volume Tests
    @patch('skills.volume_control._adapter')
    def test_volume_up(self, mock_adapter):
        mock_adapter.return_value.volume_up.return_value = {"available": True, "result": "Volume is now 60 percent, Boss.", "verified": True, "success": True}
        res = orchestrator.process_command("volume up")
        self.assertIn("60 percent", res)

    @patch('skills.volume_control._adapter')
    def test_volume_down(self, mock_adapter):
        mock_adapter.return_value.volume_down.return_value = {"available": True, "result": "Volume is now 40 percent, Boss.", "verified": True, "success": True}
        res = orchestrator.process_command("volume down")
        self.assertIn("40 percent", res)

    @patch('skills.volume_control._adapter')
    def test_mute_unmute(self, mock_adapter):
        mock_adapter.return_value.mute.return_value = {"available": True, "result": "Volume muted Boss.", "verified": True, "success": True}
        res = orchestrator.process_command("mute")
        self.assertIn("Volume muted", res)

    @patch('skills.volume_control._adapter')
    def test_absolute_volume(self, mock_adapter):
        mock_adapter.return_value.set_volume.return_value = {"available": True, "result": "Volume set to 50% Boss.", "verified": True, "success": True}
        res = orchestrator.process_command("set volume to 50")
        self.assertIn("Volume set to 50%", res)
        mock_adapter.return_value.set_volume.assert_called_with(0.5)

    # Token Lifecycles & Security tests
    def test_token_expiry_validation(self):
        orchestrator.process_command("shutdown pc")
        self.assertIsNotNone(session.pending_confirmation)
        # Manually backdate the confirmation creation time to trigger timeout
        session.pending_confirmation["created_at"] = time.time() - 30.0
        res = orchestrator.process_command("yes")
        self.assertIn("timed out", res.lower())
        self.assertIsNone(session.pending_confirmation)

    def test_token_single_use(self):
        orchestrator.process_command("shutdown pc")
        with patch('skills.windows_control._adapter') as mock_adapter:
            mock_adapter.return_value.shutdown.return_value = {"available": True, "result": "Shutting down computer Boss.", "verified": True, "success": True}
            res = orchestrator.process_command("yes")
            self.assertIn("Goodbye, Boss", res)
            self.assertIsNone(session.pending_confirmation)
            
            # Second call to yes should do nothing
            res2 = orchestrator.process_command("yes")
            self.assertEqual(res2, "Waiting Boss")

    def test_no_pending_action_yes_ignored(self):
        res = orchestrator.process_command("yes")
        self.assertEqual(res, "Waiting Boss")

    # Adapter Boundary Conditions
    @patch('ultron_platform.windows_adapter.WindowsAdapter._get_volume_interface')
    def test_volume_adapter_boundaries(self, mock_get_vol):
        mock_vol = MagicMock()
        mock_vol.GetMasterVolumeLevelScalar.return_value = 0.5
        mock_get_vol.return_value = mock_vol
        
        adapter = WindowsAdapter()
        
        # Test 100% boundary
        res = adapter.set_volume(1.5)
        self.assertTrue(res["success"])
        mock_vol.SetMasterVolumeLevelScalar.assert_called_with(1.0, None)
        
        # Test 0% boundary
        res = adapter.set_volume(-0.5)
        self.assertTrue(res["success"])
        mock_vol.SetMasterVolumeLevelScalar.assert_called_with(0.0, None)

    # Routing & Bypass LLM
    @patch('brain.llm_manager.LLMManager.ask')
    def test_dangerous_commands_bypass_llm(self, mock_llm_ask):
        orchestrator.process_command("restart pc")
        mock_llm_ask.assert_not_called()

    @patch('brain.llm_manager.LLMManager.ask')
    def test_volume_commands_bypass_llm(self, mock_llm_ask):
        with patch('skills.volume_control._adapter') as mock_adapter:
            mock_adapter.return_value.volume_up.return_value = {"available": True, "result": "Volume is now 60 percent, Boss.", "verified": True, "success": True}
            orchestrator.process_command("volume up")
            mock_llm_ask.assert_not_called()

if __name__ == "__main__":
    unittest.main()
