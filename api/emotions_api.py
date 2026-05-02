from fastapi import APIRouter
from authorization import login_required
from utils.api_response import apiResponse, ApiError
from utils.connection_manager import manager
from settings import app, emotion_registry
from services.emotion_registry import EmotionNotFoundError
from api.schemas.emotions import (
    EmotionResponse, SetEmotionRequest, EmotionListResponse, EmotionSetResponse,
)

router = APIRouter(prefix="/api/emotions", tags=["Emotions"])

async def _broadcast_change(emotion: str, source: str) -> None:
    await manager.broadcast({
        "event": "system.emotion_changed",
        "data": {"emotion": emotion, "source": source},
    })

@router.get("/current",
    response_model=EmotionResponse,
    summary="Получить текущую эмоцию",
    description="Возвращает текущую эмоцию, которая отображается на лице робота."
)
async def get_current_emotion():
    return apiResponse({"emotion": emotion_registry.current})

@router.put("/current",
    response_model=EmotionSetResponse,
    summary="Изменить текущую эмоцию",
    description="Устанавливает новую эмоцию для робота и оповещает всех подключённых по WebSocket клиентов."
)
async def set_emotion_http(req: SetEmotionRequest, payload: dict = login_required()):
    try:
        emotion_registry.set_current(req.emotion)
    except EmotionNotFoundError:
        raise ApiError(400, f"Invalid emotion. Must be one of: {', '.join(emotion_registry.ids())}")

    await _broadcast_change(req.emotion, source="http")
    return apiResponse({"message": f"Emotion changed to {req.emotion}", "emotion": req.emotion})

@router.get("",
    response_model=EmotionListResponse,
    summary="Получить список всех эмоций",
    description="Возвращает полный список доступных эмоций и текущую активную эмоцию."
)
@router.get("/", response_model=EmotionListResponse, include_in_schema=False)
async def list_emotions():
    return apiResponse({
        "emotions": emotion_registry.items(),
        "current_emotion": emotion_registry.current,
    })

app.include_router(router)