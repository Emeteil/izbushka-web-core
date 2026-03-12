from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    nickname: str = Field(..., description="Никнейм пользователя для входа")
    password: str = Field(..., description="Пароль пользователя")

class LoginResponse(BaseModel):
    message: str = Field(..., description="Сообщение о статусе")
    user_id: str = Field(..., description="ID пользователя")
    nickname: str = Field(..., description="Никнейм пользователя")
    preferred_redirect: str = Field("/", description="URL для перенаправления после входа")

class ApiKeyResponse(BaseModel):
    token: str = Field(..., description="Сгенерированный API ключ")
