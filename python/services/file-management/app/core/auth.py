"""
Authentication middleware for File Management Service.
Supports dual token authentication: internal (backend) and frontend.
"""

from enum import Enum
from fastapi import Header, HTTPException, status
from app.core.config import settings


class TokenType(str, Enum):
    """Enum for token types."""
    INTERNAL = "internal"
    FRONTEND = "frontend"
    INVALID = "invalid"


async def verify_internal_token(authorization: str = Header(None)) -> None:
    """
    Verify internal secret key for backend service access.
    Used for Type 1 (internal-only) endpoints.

    Args:
        authorization: Authorization header with Bearer token

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "")

    if token != settings.INTERNAL_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal token",
        )


async def verify_api_access(authorization: str = Header(None)) -> TokenType:
    """
    Verify API access token (internal OR frontend).
    Used for Type 2 (signed) and Type 3 (public) write endpoints.

    Args:
        authorization: Authorization header with Bearer token

    Returns:
        TokenType: INTERNAL or FRONTEND

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "")

    # Check if it's an internal token
    if token == settings.INTERNAL_SECRET_KEY:
        return TokenType.INTERNAL

    # Check if it's a frontend token
    if token == settings.FRONTEND_API_KEY:
        return TokenType.FRONTEND

    # Neither token is valid
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid API token",
    )
