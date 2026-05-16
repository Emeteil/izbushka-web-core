from fastapi import APIRouter, Query
from dataclasses import asdict

from authorization import login_required
from utils.api_response import apiResponse, ApiError
from utils.connection_manager import manager
from settings import app, questions_log
from api.schemas.questions import (
    QuestionCreate,
    QuestionListResponse,
    QuestionStatsResponse,
    QuestionCreatedResponse,
)

router = APIRouter(prefix="/api/questions", tags=["Questions"])

@router.post(
    "",
    response_model=QuestionCreatedResponse,
    summary="Зафиксировать вопрос абитуриента",
    description="Сохраняет вопрос (и опционально ответ) с указанием темы и источника.",
)
async def create_question(payload_in: QuestionCreate, _auth: dict = login_required()):
    entry = questions_log.add(
        question=payload_in.question,
        answer=payload_in.answer,
        topic=payload_in.topic,
        source=payload_in.source,
        extra=payload_in.extra,
    )
    item = asdict(entry)
    await manager.broadcast({"event": "question.logged", "data": item})
    return apiResponse(item)


@router.get(
    "/recent",
    response_model=QuestionListResponse,
    summary="Последние вопросы",
)
async def list_recent(
    limit: int = Query(50, ge=1, le=500),
    topic: str | None = Query(None),
    _auth: dict = login_required(),
):
    items = [asdict(e) for e in questions_log.recent(limit=limit, topic=topic)]
    return apiResponse({"items": items, "total": len(items)})


@router.get(
    "/stats",
    response_model=QuestionStatsResponse,
    summary="Статистика по вопросам",
)
async def stats(_auth: dict = login_required()):
    return apiResponse(questions_log.stats())


@router.delete(
    "",
    summary="Очистить журнал вопросов",
)
async def clear(_auth: dict = login_required()):
    removed = questions_log.clear()
    await manager.broadcast({"event": "question.cleared", "data": {"removed": removed}})
    return apiResponse({"removed": removed})


app.include_router(router)