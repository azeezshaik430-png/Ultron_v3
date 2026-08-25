"""
ULTRON V3 - Real-Time UI Gateway Server
FastAPI entry point serving static UI files, WebSocket streaming, and REST API endpoints.
"""

import os
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from api.routes_security import router as security_router
from api.websocket_manager import get_ws_manager
from ultron_platform import get_platform_adapter, platform_name


app = FastAPI(
    title="ULTRON V3 UI Gateway",
    description="Real-Time WebGL UI & WebSocket API for ULTRON V3 AI Assistant",
    version="3.0.0",
)

# Enable CORS for local & cross-device development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST Routers
app.include_router(security_router)

# Mount Static Files & Templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR) if os.path.exists(TEMPLATES_DIR) else None


@app.get("/")
async def get_index(request: Request):
    """Render main ULTRON V3 UI Single Page Application."""
    if templates and os.path.exists(os.path.join(TEMPLATES_DIR, "index.html")):
        return templates.TemplateResponse(request, "index.html", {"platform": platform_name()})
    return {"status": "ONLINE", "message": "ULTRON V3 Gateway Active. Static frontend template loading..."}


@app.get("/api/health")
async def health_check():
    """System and Platform Adapter health endpoint."""
    adapter = get_platform_adapter()
    return {
        "status": "HEALTHY",
        "platform": adapter.platform_name,
        "capabilities": adapter.get_capabilities(),
        "timestamp": time.time(),
    }


@app.get("/api/memory")
async def get_memories(limit: int = 20):
    """
    Hydration endpoint for UI MemoryRecall panel.
    Returns bounded, deterministically ordered list of stored memories.
    """
    from brain.memory import load_memory
    memories = load_memory()
    items = []
    for key in sorted(memories.keys()):
        val = memories[key]
        tag = "PREFERENCE" if key in ["name", "likes", "favorite_game", "laptop", "phone", "project"] else "SEMANTIC"
        items.append({
            "key": key,
            "value": str(val),
            "tag": tag,
            "text": f"{key}: {val}"
        })
    return {"total": len(items), "memories": items[:limit]}


from pydantic import BaseModel
from fastapi import HTTPException


class CommandRequest(BaseModel):
    command: str


@app.post("/api/command")
async def execute_command(req: CommandRequest):
    """
    Execute a user command via Orchestrator.
    Emits real-time AgentBus/EventBus events to connected WebSocket clients.
    """
    if not req.command or not req.command.strip():
        raise HTTPException(status_code=400, detail="Command text cannot be empty.")

    from brain.orchestrator import orchestrator
    from core.event_bus import event_bus
    result = orchestrator.process_command(req.command)
    event_bus.publish("ASSISTANT_RESPONSE", text=result)
    return {"success": True, "command": req.command, "result": result}


@app.websocket("/ws/ui")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket Gateway Endpoint for real-time UI streaming.
    """
    ws_manager = get_ws_manager()
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Process inbound messages if needed (e.g. ping/pong, user prompts)
            event_type = data.get("event")
            if event_type == "ping":
                await websocket.send_json({"event": "pong", "timestamp": time.time()})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
