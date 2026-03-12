from fastapi import APIRouter, Request
from utils.api_response import apiResponse, ApiError
from utils.api_models import ApiResponse
from settings import app

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/ping", 
    summary="Проверить доступность сервера",
    description="Возвращает 'Pong!', если сервер работает корректно."
)
async def ping_server():
    return apiResponse({"message": "Pong!"})

@app.get("/error_page", include_in_schema=False)
async def error_page_cheack(request: Request):
    status_code: int = int(request.query_params.get("code", 500))
    raise ApiError(
        code = status_code
    )

app.include_router(router)