"""
AI chatbot endpoints (StevenAI).
"""

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import HTTPClient
from app.clients import stevenai_client
from shared_schemas.web_server import ChatQueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/query", response_model=ChatQueryResponse)
async def query_chat(
    client: HTTPClient,
    q: str = Query(..., description="User question"),
    model: str = Query(default="gpt4o", description="Model to use (gpt4o, llama)"),
    context: str = Query(default="qa-docs", description="Context source (qa, docs, qa-docs)"),
    last_q: str | None = Query(default=None, description="Previous question for follow-up"),
    last_a: str | None = Query(default=None, description="Previous answer for follow-up")
):
    """
    Query AI chatbot about Steven.

    This endpoint will route to stevenai-service in Phase 2.
    Currently returns 501 Not Implemented.

    Args:
        q: User question
        model: Model to use (gpt4o or llama)
        context: Context source (qa, docs, or qa-docs)
        last_q: Previous question for follow-up context
        last_a: Previous answer for follow-up context

    Returns:
        AI-generated answer with context sources
    """
    logger.warning(f"Chat query requested: '{q}' with model={model}, context={context}, but service not implemented")

    # Validate model
    if model not in ["gpt4o", "llama"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model: {model}. Supported models: gpt4o, llama"
        )

    # Validate context
    if context not in ["qa", "docs", "qa-docs"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid context: {context}. Supported contexts: qa, docs, qa-docs"
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "StevenAI service not yet implemented",
            "phase": "Phase 2",
            "query": q,
            "model": model,
            "context": context,
            "next_steps": "This will route to a separate stevenai-service microservice with RAG"
        }
    )
