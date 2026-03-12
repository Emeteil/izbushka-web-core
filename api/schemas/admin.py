from pydantic import BaseModel, Field

class PingResponse(BaseModel):
    message: str = Field(..., description="Сообщение ответа на пинг", json_schema_extra={"example": "Pong!"})