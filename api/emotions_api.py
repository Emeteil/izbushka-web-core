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
    description="Возвращает текущую эмоцию, которая отображается на роботе."
)
async def get_current_emotion():
    return apiResponse({"emotion": g_settings.current_emotion})

@router.post("/set", 
    response_model=EmotionSetResponse, 
    summary="Установить новую эмоцию", 
    description="Изменяет текущую эмоцию робота и оповещает всех подключенных клиентов через WebSocket."
)
async def set_emotion_http(req: SetEmotionRequest, payload: dict = login_required()):
    emotion = req.emotion
    valid_emotions = settings["emotions"]["ids"]
    
    if emotion not in valid_emotions:
        raise ApiError(400, f"Invalid emotion. Must be one of: {', '.join(valid_emotions)}")
    
    g_settings.current_emotion = emotion
    
    await manager.broadcast({
        "event": "emotion_changed",
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
    description="Возвращает список всех доступных эмоций и текущую активную эмоцию."
)
@router.get("/list", 
    response_model=EmotionListResponse, 
    summary="Получить список всех эмоций", 
    description="Возвращает список всех доступных эмоций и текущую активную эмоцию."
)
async def list_emotions():
    return apiResponse({
        "emotions": settings["emotions"]["items"],
        "current_emotion": g_settings.current_emotion
    })

app.include_router(router)