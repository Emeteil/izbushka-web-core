from fastapi import APIRouter, Request, Response
from utils.api_response import apiResponse, ApiError
from authorization import login_required, generate_token
from utils.validation.user_data import NICKNAME_LENGTH, PASSWORD_LENGTH
from utils.password_hash import check_password_hash
from utils.db.users import get_user_by_nickname
from settings import app, limiter
from api.schemas.auth import LoginRequest, LoginResponse, ApiKeyResponse

router = APIRouter(prefix="/api/authorization", tags=["Authorization"])

@router.post("/login", 
    response_model=LoginResponse, 
    summary="Авторизация пользователя", 
    description="Позволяет пользователю войти в систему по никнейму и паролю, возвращает токен доступа в cookie."
)
@limiter.limit("6 per 3 minute")
async def api_login(request: Request, response: Response, req: LoginRequest):
    nickname = req.nickname[:NICKNAME_LENGTH[1]]
    password = req.password[:PASSWORD_LENGTH[1]]

    if not nickname or not password:
        raise ApiError(400, 'Need "nickname" and "password" in data!')

    user = get_user_by_nickname(nickname)
    
    if not user or not check_password_hash(user["password_hash"], password):
        raise ApiError(401, "Invalid nickname or password!")
    
    token: str = generate_token(user["id"], user["nickname"])
    
    resp_data = {
        "message": "Login successful",
        "user_id": user["id"],
        "nickname": user["nickname"],
        "preferred_redirect": "/control"
    }
    
    api_resp = apiResponse(resp_data, 200)
    api_resp.set_cookie(key="token", value=token)
    
    return api_resp

@router.post("/request_api_key", 
    response_model=ApiKeyResponse, 
    summary="Запросить API ключ", 
    description="Генерирует и возвращает новый API ключ (токен) для авторизованного пользователя."
)
@limiter.limit("5 per 30 minute")
async def api_request_api_key(request: Request, payload: dict = login_required()):
    token: str = generate_token(payload["user_id"], payload["nickname"])
    
    return apiResponse({
        "token": token
    }, 201)

app.include_router(router)