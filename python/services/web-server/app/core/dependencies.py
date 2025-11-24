"""
Shared dependencies for FastAPI endpoints.
"""

import logging
from typing import Annotated

from fastapi import Depends
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# HTTP Client singleton
_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    """
    Get or create the global HTTP client.
    Used for making requests to downstream services.
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=settings.PROXMOX_VERIFY_SSL
        )
    return _http_client


async def close_http_client():
    """Close the global HTTP client."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


# Dependency annotation
HTTPClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
