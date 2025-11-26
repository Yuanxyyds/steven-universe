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
    Used for making requests to downstream services (file-service).
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=None),  # Allow streaming
            follow_redirects=True
        )
    return _http_client


async def close_http_client():
    """Close the global HTTP client."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


async def verify_api_key(x_api_key: Annotated[str, Header()]):
    """
    Verify API key from request header.
    Raises 401 if invalid or missing.
    """
    if x_api_key != settings.INTERNAL_API_KEY:
        logger.warning(f"Invalid API key attempted: {x_api_key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return x_api_key


# Dependency annotations
HTTPClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
APIKey = Annotated[str, Depends(verify_api_key)]
