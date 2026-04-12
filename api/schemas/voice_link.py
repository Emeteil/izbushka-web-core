from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class VoiceLinkStatusResponse(BaseModel):
    connected: bool = Field(..., description="Подключён ли voice-interface")
    status: str = Field(..., description="Текущее состояние: disconnected, idle, wake_word_detected, active")
    last_message: Optional[Dict[str, Any]] = Field(None, description="Последнее сообщение от ассистента")
    last_tool_call: Optional[Dict[str, Any]] = Field(None, description="Последний вызов инструмента")
    last_error: Optional[str] = Field(None, description="Последняя ошибка")
    connected_at: Optional[str] = Field(None, description="Время подключения")
    updated_at: Optional[str] = Field(None, description="Время последнего обновления")

class VoiceLinkCommandResponse(BaseModel):
    message: str = Field(..., description="Результат отправки команды")