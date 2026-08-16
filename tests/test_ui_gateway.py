"""
ULTRON V3 - UI Gateway Integration Test Suite
Verifies FastAPI endpoints, WebSocket gateway streaming, security token validation,
and event contract compliance.
"""

import time
import unittest
import threading
import _thread
import contextlib
from fastapi.testclient import TestClient

from api.app import app
from api.websocket_manager import get_ws_manager
from core.session import session


@contextlib.contextmanager
def timeout_limit(seconds=5.0):
    """Context manager to raise KeyboardInterrupt if execution takes too long."""
    timer = threading.Timer(seconds, lambda: _thread.interrupt_main())
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


class TestUIGatewayREST(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint_returns_healthy(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertIn("platform", data)
        self.assertIn("capabilities", data)

    def test_index_route_returns_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_security_confirm_without_pending_token_returns_400(self):
        session.clear_pending_confirmation()
        response = self.client.post("/api/security/confirm", json={"token_id": "invalid", "approved": True})
        self.assertEqual(response.status_code, 400)

    def test_security_confirm_with_valid_token_succeeds(self):
        token_data = session.set_pending_confirmation(
            action="shutdown_pc",
            command="shutdown /s"
        )
        response = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": True},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("authorized", data["message"].lower())

    def test_security_confirm_with_mocked_action_executes_once(self):
        from unittest.mock import MagicMock
        mock_action = MagicMock(return_value="Success")
        token_data = session.set_pending_confirmation(
            action="shutdown_pc",
            command="shutdown /s",
            exec_func=mock_action
        )
        response = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": True},
        )
        self.assertEqual(response.status_code, 200)
        mock_action.assert_called_once()
        self.assertIsNone(session.pending_confirmation)

    def test_security_confirm_invalid_token_does_not_execute(self):
        from unittest.mock import MagicMock
        mock_action = MagicMock(return_value="Success")
        token_data = session.set_pending_confirmation(
            action="shutdown_pc",
            command="shutdown /s",
            exec_func=mock_action
        )
        response = self.client.post(
            "/api/security/confirm",
            json={"token_id": "invalid_token_id_value", "approved": True},
        )
        self.assertEqual(response.status_code, 403)
        mock_action.assert_not_called()
        self.assertIsNotNone(session.pending_confirmation)

    def test_security_confirm_expired_token_does_not_execute(self):
        from unittest.mock import MagicMock
        mock_action = MagicMock(return_value="Success")
        token_data = session.set_pending_confirmation(
            action="shutdown_pc",
            command="shutdown /s",
            exec_func=mock_action,
            timeout_seconds=-1.0
        )
        response = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": True},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["detail"].lower())
        mock_action.assert_not_called()
        self.assertIsNone(session.pending_confirmation)

    def test_security_confirm_rejected_does_not_execute(self):
        from unittest.mock import MagicMock
        mock_action = MagicMock(return_value="Success")
        token_data = session.set_pending_confirmation(
            action="shutdown_pc",
            command="shutdown /s",
            exec_func=mock_action
        )
        response = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": False},
        )
        self.assertEqual(response.status_code, 200)
        mock_action.assert_not_called()
        self.assertIsNone(session.pending_confirmation)

    def test_security_confirm_callback_failure_handles_gracefully(self):
        from unittest.mock import MagicMock
        mock_action = MagicMock(side_effect=Exception("OS call failed"))
        token_data = session.set_pending_confirmation(
            action="shutdown_pc",
            command="shutdown /s",
            exec_func=mock_action
        )
        response = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": True},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("failed", response.json()["detail"].lower())
        mock_action.assert_called_once()
        self.assertIsNone(session.pending_confirmation)

    def test_security_confirm_reuse_protection(self):
        from unittest.mock import MagicMock
        mock_action = MagicMock(return_value="Success")
        token_data = session.set_pending_confirmation(
            action="shutdown_pc",
            command="shutdown /s",
            exec_func=mock_action
        )
        response1 = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": True},
        )
        self.assertEqual(response1.status_code, 200)
        
        response2 = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": True},
        )
        self.assertEqual(response2.status_code, 400)
        mock_action.assert_called_once()

    def test_real_shutdown_execution_flow_with_mock_adapter(self):
        from skills.windows_control import shutdown_pc
        from unittest.mock import patch, MagicMock
        import ultron_platform
        from core.config import config
        
        mock_adapter = MagicMock()
        mock_adapter.shutdown.return_value = {"available": True, "result": "Success", "verified": True, "success": True}
        
        with patch("ultron_platform.get_platform_adapter", return_value=mock_adapter):
            with patch.object(config, "SAFE_PHYSICAL_TEST_MODE", False):
                token_data = session.set_pending_confirmation(
                    action="shutdown_pc",
                    command="shutdown pc",
                    exec_func=shutdown_pc
                )
                response = self.client.post(
                    "/api/security/confirm",
                    json={"token_id": token_data["id"], "approved": True},
                )
                self.assertEqual(response.status_code, 200)
                mock_adapter.shutdown.assert_called_once()
                self.assertIsNone(session.pending_confirmation)

    def test_real_restart_execution_flow_with_mock_adapter(self):
        from skills.windows_control import restart_pc
        from unittest.mock import patch, MagicMock
        import ultron_platform
        from core.config import config
        
        mock_adapter = MagicMock()
        mock_adapter.restart.return_value = {"available": True, "result": "Success", "verified": True, "success": True}
        
        with patch("ultron_platform.get_platform_adapter", return_value=mock_adapter):
            with patch.object(config, "SAFE_PHYSICAL_TEST_MODE", False):
                token_data = session.set_pending_confirmation(
                    action="restart_pc",
                    command="restart pc",
                    exec_func=restart_pc
                )
                response = self.client.post(
                    "/api/security/confirm",
                    json={"token_id": token_data["id"], "approved": True},
                )
                self.assertEqual(response.status_code, 200)
                mock_adapter.restart.assert_called_once()
                self.assertIsNone(session.pending_confirmation)

    def test_real_lock_execution_flow_with_mock_adapter(self):
        from skills.windows_control import lock_pc
        from unittest.mock import patch, MagicMock
        import ultron_platform
        
        mock_adapter = MagicMock()
        mock_adapter.lock.return_value = {"available": True, "result": "Success", "verified": True, "success": True}
        
        with patch("ultron_platform.get_platform_adapter", return_value=mock_adapter):
            token_data = session.set_pending_confirmation(
                action="lock_pc",
                command="lock pc",
                exec_func=lock_pc
            )
            response = self.client.post(
                "/api/security/confirm",
                json={"token_id": token_data["id"], "approved": True},
            )
            self.assertEqual(response.status_code, 200)
            mock_adapter.lock.assert_called_once()
            self.assertIsNone(session.pending_confirmation)



class TestUIGatewayWebSocket(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_websocket_connect_and_handshake(self):
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                data = websocket.receive_json()
                self.assertEqual(data["event"], "connection_state")
                self.assertTrue(data["payload"]["connected"])

    def test_websocket_ping_pong(self):
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                websocket.send_json({"event": "ping"})
                response = websocket.receive_json()
                self.assertEqual(response["event"], "pong")

    def test_ws_manager_broadcast(self):
        ws_manager = get_ws_manager()
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                ws_manager.broadcast_sync("voice_state", {"state": "LISTENING"})
                response = websocket.receive_json()
                self.assertEqual(response["event"], "voice_state")
                self.assertEqual(response["payload"]["state"], "LISTENING")


if __name__ == "__main__":
    unittest.main()
