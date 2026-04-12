from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from authorization import login_required
from utils.api_response import apiResponse, ApiError
from utils.connection_manager import manager
from settings import app, settings
from api.schemas.voice_link import VoiceLinkStatusResponse, VoiceLinkCommandResponse
from datetime import datetime
from typing import Optional
import json
import logging

logger = logging.getLogger("voice_link")

router = APIRouter(prefix="/api/voice", tags=["Voice Link"])

class VoiceLinkState:
    def __init__(self):
        self.connected: bool = False
        self.status: str = "disconnected"
        self.last_message: Optional[dict] = None
        self.last_tool_call: Optional[dict] = None
        self.last_error: Optional[str] = None
        self.connected_at: Optional[str] = None
        self.updated_at: Optional[str] = None
        self._ws: Optional[WebSocket] = None

    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "status": self.status,
            "last_message": self.last_message,
            "last_tool_call": self.last_tool_call,
            "last_error": self.last_error,
            "connected_at": self.connected_at,
            "updated_at": self.updated_at,
        }

    def update_timestamp(self):
        self.updated_at = datetime.now().isoformat()

    async def send_command(self, event: str, data: dict = None) -> bool:
        if not self._ws or not self.connected:
            return False
        try:
            await self._ws.send_json({"event": event, "data": data or {}})
            return True
        except Exception:
            return False


voice_state = VoiceLinkState()


@router.websocket("/link")
async def voice_link_ws(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if token != settings.get("MASTER_TOKEN"):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    if voice_state.connected:
        await websocket.close(code=4002, reason="Already connected")
        return

    await websocket.accept()

    voice_state._ws = websocket
    voice_state.connected = True
    voice_state.status = "idle"
    voice_state.last_error = None
    voice_state.connected_at = datetime.now().isoformat()
    voice_state.update_timestamp()

    logger.info("Voice interface connected")

    await manager.broadcast({
        "event": "voice.connected",
        "data": voice_state.to_dict()
    })

    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                event = msg.get("event", "")
                data = msg.get("data", {})

                voice_state.update_timestamp()

                if event == "voice.status_changed":
                    voice_state.status = data.get("status", voice_state.status)
                elif event == "voice.message":
                    voice_state.last_message = data
                elif event == "voice.tool_call":
                    voice_state.last_tool_call = data
                elif event == "voice.error":
                    voice_state.last_error = data.get("message")

                await manager.broadcast({"event": event, "data": data})

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        logger.info("Voice interface disconnected")
    except Exception as e:
        logger.error(f"Voice link error: {e}")
    finally:
        voice_state.connected = False
        voice_state.status = "disconnected"
        voice_state._ws = None
        voice_state.update_timestamp()

        await manager.broadcast({
            "event": "voice.disconnected",
            "data": voice_state.to_dict()
        })


@router.get("/status",
    response_model=VoiceLinkStatusResponse,
    summary="Статус голосового интерфейса",
    description="Возвращает текущее состояние voice-interface: подключение, статус ассистента, последние события."
)
async def get_voice_status(payload: dict = login_required()):
    return apiResponse(voice_state.to_dict())


@router.post("/trigger",
    response_model=VoiceLinkCommandResponse,
    summary="Вызвать ассистента",
    description="Отправляет команду запуска голосового ассистента без необходимости произнесения wake word."
)
async def trigger_voice(payload: dict = login_required()):
    if not voice_state.connected:
        raise ApiError(503, "Voice interface not connected")
    if voice_state.status == "active":
        raise ApiError(409, "Voice assistant is already active")

    success = await voice_state.send_command("voice.trigger")
    if not success:
        raise ApiError(502, "Failed to send trigger command")

    return apiResponse({"message": "Trigger command sent"})


@router.post("/stop",
    response_model=VoiceLinkCommandResponse,
    summary="Остановить ассистента",
    description="Отправляет команду остановки активной сессии голосового ассистента."
)
async def stop_voice(payload: dict = login_required()):
    if not voice_state.connected:
        raise ApiError(503, "Voice interface not connected")
    if voice_state.status != "active":
        raise ApiError(409, "Voice assistant is not active")

    success = await voice_state.send_command("voice.stop")
    if not success:
        raise ApiError(502, "Failed to send stop command")

    return apiResponse({"message": "Stop command sent"})


app.include_router(router)