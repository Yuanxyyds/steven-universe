"""
Health check endpoint.
"""

from fastapi import APIRouter

from app.core.config import settings
from shared_schemas.stevenai_service import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check."""
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION
    )
