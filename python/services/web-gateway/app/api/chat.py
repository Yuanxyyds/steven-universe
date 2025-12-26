"""
AI chatbot endpoints (StevenAI).
"""

import logging

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import HTTPClient, verify_api_key
from app.clients import stevenai_client
from shared_schemas.stevenai_service import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/stream")
async def chat_stream(
    client: HTTPClient,
    request: ChatRequest,
    _: None = Depends(verify_api_key)
):
    """
    Stream chat completion with RAG from stevenai-service.

    This endpoint routes to stevenai-service which handles:
    - Follow-up question rewriting (if last_q and last_a provided)
    - RAG context retrieval (documents and/or QA pairs)
    - Model routing (chatGPT, Qwen, Llama)
    - Streaming response with character buffering

    Args:
        request: Chat request with query, optional history, model selection, and RAG flags

    Returns:
        SSE stream with chat response chunks
    """
    logger.info(
        f"Chat stream request: model={request.model}, "
        f"query={request.query[:50]}..., "
        f"has_history={bool(request.last_q and request.last_a)}, "
        f"use_docs={request.use_docs_of_fact}, use_qa={request.use_qa_pairs}"
    )

    async def event_generator():
        async for chunk in stevenai_client.stream_chat(client, request):
            yield chunk

    return EventSourceResponse(event_generator())
