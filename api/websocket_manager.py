"""
ULTRON V3 - WebSocket Connection Manager & AgentBus Bridge
Manages live WebSocket clients and streams AgentBus topics to connected UI clients.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Set
from fastapi import WebSocket

from brain.agent_bus import AgentMemoryBus
from core.event_bus import event_bus
from core.session import session
from ultron_platform import platform_name


class WebSocketManager:
    """
    WebSocket Client Connection Manager.
    Broadcasts UI events and bridges AgentBus events to real-time WebSockets.
    """

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._bus = AgentMemoryBus()
        self._subscribed = False
        self._telemetry_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.loop = asyncio.get_running_loop()

        # Send initial handshake state
        await self.send_personal_message(
            {
                "event": "connection_state",
                "timestamp": time.time(),
                "payload": {"connected": True, "version": "3.0.0", "status": "ONLINE"},
            },
            websocket,
        )

        if not self._subscribed:
            self._setup_agent_bus_bridge()

        if (self._telemetry_task is None or self._telemetry_task.done()) and self.active_connections:
            self._telemetry_task = asyncio.create_task(self._run_telemetry_loop())

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        if not self.active_connections and self._telemetry_task and not self._telemetry_task.done():
            self._telemetry_task.cancel()
            self._telemetry_task = None

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        dead_sockets = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_sockets.add(connection)
        for dead in dead_sockets:
            self.active_connections.discard(dead)

    def broadcast_sync(self, event_name: str, payload: dict):
        """Thread-safe synchronous broadcast for background AgentBus/EventBus callbacks."""
        msg = {
            "event": event_name,
            "timestamp": time.time(),
            "payload": payload,
        }
        loop = getattr(self, "loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(msg), loop)
        else:
            try:
                current_loop = asyncio.get_running_loop()
                if current_loop.is_running():
                    current_loop.create_task(self.broadcast(msg))
            except RuntimeError:
                pass

    async def _run_telemetry_loop(self):
        """Periodically broadcast system metrics telemetry while clients are connected."""
        import psutil
        try:
            while self.active_connections:
                await asyncio.sleep(2.0)
                if not self.active_connections:
                    break
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                self.broadcast_sync("system_metrics", {
                    "cpu_percent": float(cpu),
                    "ram_percent": float(ram),
                    "platform": platform_name(),
                })
        except asyncio.CancelledError:
            pass
        finally:
            self._telemetry_task = None

    def _setup_agent_bus_bridge(self):
        """Subscribe to AgentBus / EventBus topics and stream events to WebSocket subscribers."""
        self._subscribed = True

        def _on_agent_event(event):
            self.broadcast_sync("agent_progress", {
                "agent_name": getattr(event, "source_agent", None) or "Agent",
                "task_id": getattr(event, "task_id", None) or "task",
                "step": str(getattr(event, "payload", event)),
                "progress": 0.5,
            })

        def _on_voice_state_changed(state: str = "IDLE", **kwargs):
            self.broadcast_sync("voice_state", {"state": state, "timestamp": time.time()})

        def _on_speech_recognized(text: str = "", language: str = "en", is_final: bool = True, **kwargs):
            self.broadcast_sync("speech_recognized", {"text": text, "language": language, "is_final": is_final})

        def _on_assistant_response(text: str = "", intent: str = "", agent: str = "", speak: bool = True, **kwargs):
            self.broadcast_sync("assistant_response", {"text": text, "intent": intent, "agent": agent, "speak": speak})

        def _on_agent_progress(agent_name: str = "Agent", task_id: str = "task", step: str = "", progress: float = 0.5, **kwargs):
            self.broadcast_sync("agent_progress", {
                "agent_name": agent_name,
                "task_id": task_id,
                "step": step,
                "progress": progress,
            })

        def _on_security_confirmation(conf_data: dict):
            token_id = conf_data.get("id") or conf_data.get("confirmation_id")
            action = conf_data.get("action", "action")
            command = conf_data.get("command", "")
            expires_in = int(conf_data.get("timeout_seconds", 15))
            self.broadcast_sync("security_confirmation_required", {
                "token_id": token_id,
                "action": action,
                "target": command or "Local Host",
                "expires_in": expires_in,
            })
            self.broadcast_sync("voice_state", {"state": "WAITING_CONFIRMATION", "timestamp": time.time()})

        # Register event_bus subscribers
        try:
            event_bus.subscribe("VOICE_STATE_CHANGED", _on_voice_state_changed)
            event_bus.subscribe("SPEECH_RECOGNIZED", _on_speech_recognized)
            event_bus.subscribe("ASSISTANT_RESPONSE", _on_assistant_response)
            event_bus.subscribe("AGENT_PROGRESS", _on_agent_progress)
            event_bus.subscribe(event_bus.TASK_STARTED, lambda command="": _on_voice_state_changed("PROCESSING"))
            event_bus.subscribe(event_bus.TASK_FINISHED, lambda command="": _on_voice_state_changed("IDLE"))
        except Exception:
            pass

        # Register session confirmation listener
        try:
            session.register_confirmation_listener(_on_security_confirmation)
        except Exception:
            pass


_ws_manager_instance = None


def get_ws_manager() -> WebSocketManager:
    global _ws_manager_instance
    if _ws_manager_instance is None:
        _ws_manager_instance = WebSocketManager()
    return _ws_manager_instance

