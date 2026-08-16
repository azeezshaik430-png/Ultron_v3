"""
ULTRON V3 - UI Gateway Event Contract Schemas
Defines typed JSON RPC payload schemas for backend <-> frontend WebSocket communication.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UIState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    EXECUTING = "EXECUTING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"


class WebSocketEvent(BaseModel):
    event: str = Field(..., description="Name of the event")
    timestamp: float = Field(..., description="Unix timestamp of event generation")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Typed payload data")


class VoiceStatePayload(BaseModel):
    state: UIState
    timestamp: float


class AudioLevelPayload(BaseModel):
    source: str  # "mic" or "tts"
    amplitude: float
    frequencies: Optional[List[float]] = None


class SpeechRecognizedPayload(BaseModel):
    text: str
    language: str = "en"
    is_final: bool = True


class AssistantResponsePayload(BaseModel):
    text: str
    intent: Optional[str] = None
    agent: Optional[str] = None
    speak: bool = True


class AgentProgressPayload(BaseModel):
    agent_name: str
    task_id: str
    step: str
    progress: float  # 0.0 to 1.0


class SecurityConfirmationRequiredPayload(BaseModel):
    token_id: str
    action: str
    target: str
    expires_in: int = 15


class SecurityConfirmationResultPayload(BaseModel):
    token_id: str
    approved: bool


class SystemMetricsPayload(BaseModel):
    cpu_percent: float
    ram_percent: float
    platform: str
    battery: Optional[Dict[str, Any]] = None
