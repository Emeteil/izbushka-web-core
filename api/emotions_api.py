from fastapi import APIRouter, Depends
from authorization import login_required
from utils.api_response import apiResponse, ApiError
from settings import settings, app
import settings as g_settings
from api.schemas.emotions import EmotionResponse, SetEmotionRequest, EmotionListResponse, EmotionSetResponse
from utils.connection_manager import manager

router = APIRouter(prefix="/api/emotions", tags=["Emotions"])

@router.get("/current", 
    response_model=EmotionResponse,
    summary="Получить текущую эмоцию",
    description="Возвращает текущую эмоцию, которая отображается на лице робота."
)
async def get_current_emotion():
    return apiResponse({"emotion": g_settings.current_emotion})

@router.put("/current", 
    response_model=EmotionSetResponse,
    summary="Изменить текущую эмоцию",
    description="Устанавливает новую эмоцию для робота и оповещает всех подключённых по WebSocket клиентов о её изменении."
)
async def set_emotion_http(req: SetEmotionRequest, payload: dict = login_required()):
    emotion = req.emotion
    valid_emotions = settings["emotions"]["ids"]
    
    if emotion not in valid_emotions:
        raise ApiError(400, f"Invalid emotion. Must be one of: {', '.join(valid_emotions)}")
    
    g_settings.current_emotion = emotion
    
    await manager.broadcast({
        "event": "system.emotion_changed",
        "data": {
            "emotion": emotion,
            "source": "http"
        }
    })
    
    return apiResponse({
        "message": f"Emotion changed to {emotion}",
        "emotion": emotion
    })

@router.get("", 
    response_model=EmotionListResponse,
    summary="Получить список всех эмоций",
    description="Возвращает полный список доступных эмоций, которые может демонстрировать робот, а также текущую активную эмоцию."
)
@router.get("/", response_model=EmotionListResponse, include_in_schema=False)
async def list_emotions():
    return apiResponse({
        "emotions": settings["emotions"]["items"],
        "current_emotion": g_settings.current_emotion
    })

app.include_router(router)