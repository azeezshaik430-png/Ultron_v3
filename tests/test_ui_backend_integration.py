"""
ULTRON V3 - UI Backend Integration Test Suite
Verifies 14-point contract for UI <-> FastAPI <-> WebSocket <-> AgentBus integration.
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
from core.event_bus import event_bus


@contextlib.contextmanager
def timeout_limit(seconds=5.0):
    """Context manager to raise KeyboardInterrupt if test execution takes too long."""
    timer = threading.Timer(seconds, lambda: _thread.interrupt_main())
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


class TestUIBackendIntegration(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        session.reset()

    def tearDown(self):
        session.reset()

    # 1. WebSocket connection
    def test_01_websocket_connection_handshake(self):
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                data = websocket.receive_json()
                self.assertEqual(data["event"], "connection_state")
                self.assertTrue(data["payload"]["connected"])
                self.assertEqual(data["payload"]["status"], "ONLINE")

    # 2. Backend event -> WebSocket event bridge
    def test_02_backend_event_to_websocket_bridge(self):
        ws_manager = get_ws_manager()
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                event_bus.publish("VOICE_STATE_CHANGED", state="PROCESSING")
                data = websocket.receive_json()
                self.assertEqual(data["event"], "voice_state")
                self.assertEqual(data["payload"]["state"], "PROCESSING")

    # 3. Real state transitions
    def test_03_real_state_transitions(self):
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                event_bus.publish("VOICE_STATE_CHANGED", state="LISTENING")
                d1 = websocket.receive_json()
                self.assertEqual(d1["payload"]["state"], "LISTENING")

                event_bus.publish("VOICE_STATE_CHANGED", state="SPEAKING")
                d2 = websocket.receive_json()
                self.assertEqual(d2["payload"]["state"], "SPEAKING")

    # 4. Speech recognized event
    def test_04_speech_recognized_event(self):
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                event_bus.publish("SPEECH_RECOGNIZED", text="open browser", language="en", is_final=True)
                data = websocket.receive_json()
                self.assertEqual(data["event"], "speech_recognized")
                self.assertEqual(data["payload"]["text"], "open browser")

    # 5. Assistant response event
    def test_05_assistant_response_event(self):
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                event_bus.publish("ASSISTANT_RESPONSE", text="ULTRON V3 is active", intent="system_status", agent="SystemAgent")
                data = websocket.receive_json()
                self.assertEqual(data["event"], "assistant_response")
                self.assertEqual(data["payload"]["text"], "ULTRON V3 is active")

    # 6. Agent execution/progress event
    def test_06_agent_execution_progress_event(self):
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                event_bus.publish("AGENT_PROGRESS", agent_name="BrowserAgent", task_id="t_101", step="Navigating to URL", progress=0.75)
                data = websocket.receive_json()
                self.assertEqual(data["event"], "agent_progress")
                self.assertEqual(data["payload"]["agent_name"], "BrowserAgent")
                self.assertEqual(data["payload"]["progress"], 0.75)

    # 7. Security confirmation required event
    def test_07_security_confirmation_required_event(self):
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                token_data = session.set_pending_confirmation(action="shutdown_pc", command="shutdown pc")
                d1 = websocket.receive_json()
                self.assertEqual(d1["event"], "security_confirmation_required")
                self.assertEqual(d1["payload"]["token_id"], token_data["id"])
                self.assertEqual(d1["payload"]["action"], "shutdown_pc")

    # 8. Valid security approval execution chain
    def test_08_valid_security_approval_execution_chain(self):
        from unittest.mock import MagicMock
        mock_action = MagicMock(return_value="Action Completed")
        token_data = session.set_pending_confirmation(
            action="restart_pc",
            command="restart pc",
            exec_func=mock_action
        )
        response = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": True}
        )
        self.assertEqual(response.status_code, 200)
        mock_action.assert_called_once()
        self.assertIsNone(session.pending_confirmation)

    # 9. Rejected confirmation
    def test_09_rejected_confirmation(self):
        from unittest.mock import MagicMock
        mock_action = MagicMock(return_value="Action Completed")
        token_data = session.set_pending_confirmation(
            action="shutdown_pc",
            command="shutdown pc",
            exec_func=mock_action
        )
        response = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": False}
        )
        self.assertEqual(response.status_code, 200)
        mock_action.assert_not_called()
        self.assertIsNone(session.pending_confirmation)

    # 10. Expired/invalid token
    def test_10_expired_or_invalid_token(self):
        token_data = session.set_pending_confirmation(
            action="lock_pc",
            command="lock pc",
            timeout_seconds=-1.0
        )
        res_expired = self.client.post(
            "/api/security/confirm",
            json={"token_id": token_data["id"], "approved": True}
        )
        self.assertEqual(res_expired.status_code, 400)

        res_invalid = self.client.post(
            "/api/security/confirm",
            json={"token_id": "non_existent_token", "approved": True}
        )
        self.assertEqual(res_invalid.status_code, 400)

    # 11. System telemetry delivery
    def test_11_system_telemetry_delivery(self):
        ws_manager = get_ws_manager()
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()  # Handshake
                ws_manager.broadcast_sync("system_metrics", {"cpu_percent": 15.5, "ram_percent": 42.0, "platform": "Windows"})
                data = websocket.receive_json()
                self.assertEqual(data["event"], "system_metrics")
                self.assertEqual(data["payload"]["cpu_percent"], 15.5)
                self.assertEqual(data["payload"]["ram_percent"], 42.0)

    # 12. Multiple WebSocket clients
    def test_12_multiple_websocket_clients(self):
        ws_manager = get_ws_manager()
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as ws1:
                with self.client.websocket_connect("/ws/ui") as ws2:
                    _ = ws1.receive_json()
                    _ = ws2.receive_json()
                    ws_manager.broadcast_sync("voice_state", {"state": "IDLE"})
                    d1 = ws1.receive_json()
                    d2 = ws2.receive_json()
                    self.assertEqual(d1["payload"]["state"], "IDLE")
                    self.assertEqual(d2["payload"]["state"], "IDLE")

    # 13. WebSocket disconnect cleanup
    def test_13_websocket_disconnect_cleanup(self):
        ws_manager = get_ws_manager()
        initial_count = len(ws_manager.active_connections)
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as websocket:
                _ = websocket.receive_json()
                self.assertGreaterEqual(len(ws_manager.active_connections), initial_count + 1)
        # Disconnect clean-up
        time.sleep(0.1)
        self.assertEqual(len(ws_manager.active_connections), initial_count)

    # 14. No duplicate telemetry task creation
    def test_14_no_duplicate_telemetry_task_creation(self):
        ws_manager = get_ws_manager()
        with timeout_limit(5.0):
            with self.client.websocket_connect("/ws/ui") as ws1:
                _ = ws1.receive_json()
                task1 = ws_manager._telemetry_task
                with self.client.websocket_connect("/ws/ui") as ws2:
                    _ = ws2.receive_json()
                    task2 = ws_manager._telemetry_task
                    self.assertIs(task1, task2)  # Same single telemetry task instance


if __name__ == "__main__":
    unittest.main()
