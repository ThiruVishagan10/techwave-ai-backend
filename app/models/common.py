from typing import Generic, Optional, TypeVar, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Any] = Field(default=None, description="Additional context or validation details")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    error: Optional[APIErrorDetail] = None

    @classmethod
    def success_response(cls, data: T) -> "APIResponse[T]":
        return cls(success=True, data=data, error=None)

    @classmethod
    def error_response(cls, code: str, message: str, details: Optional[Any] = None) -> "APIResponse[Any]":
        return cls(
            success=False,
            data=None,
            error=APIErrorDetail(code=code, message=message, details=details),
        )
