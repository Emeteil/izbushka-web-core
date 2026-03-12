from pydantic import BaseModel, Field

class EmotionResponse(BaseModel):
    emotion: str = Field(..., description="Текущая эмоция робота")

class SetEmotionRequest(BaseModel):
    emotion: str = Field(..., description="Эмоция для установки")

class EmotionListResponse(BaseModel):
    emotions: list[str] = Field(..., description="Список доступных эмоций")
    current_emotion: str = Field(..., description="Текущая эмоция")

class EmotionSetResponse(BaseModel):
    message: str = Field(..., description="Сообщение о результате")
    emotion: str = Field(..., description="Эмоция, которая была установлена")
