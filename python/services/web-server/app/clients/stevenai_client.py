"""
StevenAI Service Client.
Handles communication with stevenai-service microservice.
"""

import json
import logging
from typing import AsyncIterator

import httpx

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
        SSE-formatted strings with chat response chunks

    Raises:
        HTTPException: If stevenai-service is unavailable or returns error
    """
    url = f"{settings.STEVENAI_SERVICE_URL}/chat/stream"
    headers = {
        "X-API-Key": settings.STEVENAI_SERVICE_API_KEY,
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    logger.info(
        f"Streaming chat to stevenai-service: model={request.model}, "
        f"use_docs={request.use_docs_of_fact}, use_qa={request.use_qa_pairs}"
    )

    try:
        async with client.stream(
            "POST",
            url,
            json=request.model_dump(),
            headers=headers,
            timeout=httpx.Timeout(60.0, connect=5.0)
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                logger.error(
                    f"StevenAI service error: {response.status_code} - {error_text.decode()}"
                )
                # Send error event to client
                error_chunk = {
                    "type": "error",
                    "error": f"Service error: {response.status_code}"
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
                return

            # Stream SSE events from stevenai-service
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    # Forward SSE event to client
                    yield f"{line}\n\n"

    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to stevenai-service: {e}")
        error_chunk = {
            "type": "error",
            "error": "Service timeout"
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to stevenai-service: {e}")
        error_chunk = {
            "type": "error",
            "error": "Service unavailable"
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

    except Exception as e:
        logger.error(f"Error streaming from stevenai-service: {e}", exc_info=True)
        error_chunk = {
            "type": "error",
            "error": str(e)
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
