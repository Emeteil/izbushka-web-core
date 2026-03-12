from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar

T = TypeVar('T')
E = TypeVar('E')

class ResponseStatus(BaseModel):
    status: str = Field(..., description="Response status (success or error)", example="success")

class ErrorDetail(BaseModel, Generic[E]):
    code: int = Field(..., description="HTTP error code", example=400)
    message: str = Field(..., description="Error message", example="Bad Request")
    details: Optional[E] = Field(None, description="Additional error details")

class ApiResponse(ResponseStatus, Generic[T]):
    data: Optional[T] = Field(None, description="Response data")

class ApiErrorResponse(ResponseStatus, Generic[E]):
    error: ErrorDetail[E]