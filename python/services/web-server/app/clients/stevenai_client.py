"""
StevenAI service client.
Routes chat requests to the stevenai-service microservice.
"""

import logging

import httpx

from app.core.config import settings
from shared_schemas.web_server import ChatQueryRequest, ChatQueryResponse

logger = logging.getLogger(__name__)


async def query_chat(
    client: httpx.AsyncClient,
    request: ChatQueryRequest
) -> ChatQueryResponse:
    """
    Send chat query to stevenai-service.

    Args:
        client: HTTP client
        request: Chat query request

    Returns:
        Chat response from stevenai-service

    Raises:
        httpx.HTTPStatusError: If service returns error
    """
    # TODO: Implement when stevenai-service is ready
    # For now, return stub response
    logger.warning("stevenai-service not yet implemented, returning stub")

    raise NotImplementedError(
        "StevenAI service not yet implemented. "
        "This will route to a separate microservice in Phase 2."
    )
