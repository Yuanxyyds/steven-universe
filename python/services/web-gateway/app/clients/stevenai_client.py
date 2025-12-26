"""
StevenAI Service Client.
Handles communication with stevenai-service microservice.
"""

import json
import logging
from typing import AsyncIterator

import httpx
from httpx_sse import aconnect_sse

from app.core.config import settings
from shared_schemas.stevenai_service import ChatRequest

logger = logging.getLogger(__name__)


async def stream_chat(
    client: httpx.AsyncClient,
    request: ChatRequest
) -> AsyncIterator[str]:
    """
    Stream chat response from stevenai-service.

    Args:
        client: HTTP client instance
        request: Chat request with messages and model selection

    Yields:
        JSON strings with chat response chunks (not SSE-formatted)

    Raises:
        HTTPException: If stevenai-service is unavailable or returns error
    """
    url = f"{settings.STEVENAI_SERVICE_URL}/chat/stream"
    headers = {
        "X-API-Key": settings.STEVENAI_SERVICE_API_KEY,
        "Content-Type": "application/json"
    }

    logger.info(
        f"Streaming chat to stevenai-service: model={request.model}, "
        f"use_docs={request.use_docs_of_fact}, use_qa={request.use_qa_pairs}"
    )

    try:
        async with aconnect_sse(
            client,
            "POST",
            url,
            json=request.model_dump(),
            headers=headers,
            timeout=60.0
        ) as event_source:
            async for sse_event in event_source.aiter_sse():
                # Forward the data payload directly (not SSE-formatted)
                # EventSourceResponse in the endpoint will format it as SSE
                yield sse_event.data

    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to stevenai-service: {e}")
        error_chunk = {
            "type": "error",
            "error": "Service timeout"
        }
        yield json.dumps(error_chunk)

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to stevenai-service: {e}")
        error_chunk = {
            "type": "error",
            "error": "Service unavailable"
        }
        yield json.dumps(error_chunk)

    except Exception as e:
        logger.error(f"Error streaming from stevenai-service: {e}", exc_info=True)
        error_chunk = {
            "type": "error",
            "error": str(e)
        }
        yield json.dumps(error_chunk)
