from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar

T = TypeVar('T')

class WsMessage(BaseModel, Generic[T]):
    event: str = Field(..., description="Имя события", json_schema_extra={"example": "chat_message"})
    data: T = Field(..., description="Данные события")
    room_id: Optional[str] = Field(None, description="ID целевой комнаты")

class WsResponse(BaseModel, Generic[T]):
    status: str = Field(..., description="Статус ответа", json_schema_extra={"example": "ok"})
    event: str = Field(..., description="Имя события", json_schema_extra={"example": "chat_message"})
    data: T = Field(..., description="Данные ответа")
    sender_id: Optional[str] = Field(None, description="ID отправителя")