"""
Health check endpoints.
"""

import logging

from fastapi import APIRouter

from app.core.config import settings
from shared_schemas.web_server import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health_status():
    """
    Basic health check endpoint.

    Returns service status and version.
    """
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION
    )