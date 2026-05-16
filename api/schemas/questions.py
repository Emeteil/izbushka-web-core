from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    answer: Optional[str] = Field(None, max_length=4000)
    topic: Optional[str] = Field(None, max_length=64)
    source: str = Field("voice", max_length=32)
    extra: Optional[Dict[str, Any]] = None


class QuestionItem(BaseModel):
    id: str
    question: str
    answer: Optional[str]
    topic: Optional[str]
    source: str
    created_at: str
    extra: Dict[str, Any] = {}


class QuestionListData(BaseModel):
    items: List[QuestionItem]
    total: int


class QuestionListResponse(BaseModel):
    status: str
    data: QuestionListData


class QuestionStatsData(BaseModel):
    total: int
    by_topic: Dict[str, int]
    by_source: Dict[str, int]


class QuestionStatsResponse(BaseModel):
    status: str
    data: QuestionStatsData


class QuestionCreatedResponse(BaseModel):
    status: str
    data: QuestionItem