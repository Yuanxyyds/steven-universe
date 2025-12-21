"""
FastAPI dependencies for authentication and HTTP client.
"""

import httpx
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import settings

# Global HTTP client
_http_client: httpx.AsyncClient | None = None

api_key_header = APIKeyHeader(name="X-API-Key")


def get_http_client() -> httpx.AsyncClient:
    """Get or create global HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def close_http_client():
    """Close global HTTP client."""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key for authentication."""
    if api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
