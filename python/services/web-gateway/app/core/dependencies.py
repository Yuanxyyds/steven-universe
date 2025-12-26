"""
Shared dependencies for FastAPI endpoints.
"""

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
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


async def verify_api_key(x_api_key: str = Header(alias="X-API-Key")) -> None:
    """
    Verify API key from X-API-Key header.

    Args:
        x_api_key: API key from request header

    Raises:
        HTTPException: 401 if API key is missing or invalid
    """
    if not x_api_key or x_api_key != settings.API_KEY:
        logger.warning(f"Invalid API key attempt: {x_api_key[:10] if x_api_key else 'None'}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    logger.debug("API key verified successfully")
