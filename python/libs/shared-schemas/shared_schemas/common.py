"""
Common schemas and utilities shared across all services.
"""

from typing import Generic, TypeVar
from pydantic import BaseModel


T = TypeVar('T')


class SuccessResponse(BaseModel, Generic[T]):
    """
    Generic success response wrapper.

    Example:
        SuccessResponse[UploadResponse](
            success=True,
            message="File uploaded",
            data=UploadResponse(...)
        )
    """
    success: bool
    message: str | None = None
    data: T


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    detail: str
    error_code: str | None = None
