from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from authorization import get_current_user_ws
from settings import app
from typing import Dict
import logging
import uuid

logger = logging.getLogger("voice_broadcast")

router = APIRouter(prefix="/api/broadcast", tags=["Voice Broadcast"])

class VoiceBroadcastRoom:
    def __init__(self):
        self._clients: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        client_id = uuid.uuid4().hex
        self._clients[client_id] = websocket
        return client_id

    def disconnect(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    async def broadcast(self, sender_id: str, payload: bytes) -> None:
        stale = []
        for cid, ws in self._clients.items():
            if cid == sender_id:
                continue
            try:
                await ws.send_bytes(payload)
            except Exception:
                stale.append(cid)
        for cid in stale:
            self._clients.pop(cid, None)

    @property
    def listener_count(self) -> int:
        return len(self._clients)

voice_broadcast_room = VoiceBroadcastRoom()

@router.websocket("/voice")
async def voice_broadcast_ws(websocket: WebSocket):
    payload = await get_current_user_ws(websocket)
    if not payload:
        return

    client_id = await voice_broadcast_room.connect(websocket)
    logger.info(f"Voice broadcast client connected: {client_id} (total={voice_broadcast_room.listener_count})")

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data is not None:
                await voice_broadcast_room.broadcast(client_id, data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Voice broadcast error: {e}")
    finally:
        voice_broadcast_room.disconnect(client_id)
        logger.info(f"Voice broadcast client disconnected: {client_id} (total={voice_broadcast_room.listener_count})")

app.include_router(router)