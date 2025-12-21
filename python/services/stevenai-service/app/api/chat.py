"""
Chat endpoint with streaming and RAG.
"""

import json
import logging
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Depends
from sse_starlette.sse import EventSourceResponse
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.dependencies import verify_api_key
from app.services.rag_service import rag_service
from app.services.model_router import model_router
from app.services.stream_buffer import StreamBuffer
from app.clients.gpu_client import gpu_client
from shared_schemas.stevenai_service import (
    ChatRequest,
    ChatResponseChunk,
    ChatChunkType,
    RAGContext
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# OpenAI client for follow-up rewriting
openai_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL
)


async def rewrite_follow_up(
    query: str,
    last_q: Optional[str],
    last_a: Optional[str]
) -> str:
    """
    Rewrite follow-up questions as standalone queries using GPT-4o-mini.

    Follow-up questions like "What about his projects?" depend on previous context.
    This rewrites them into standalone questions like "What are Steven Liu's projects?"

    Args:
        query: Current user question
        last_q: Previous question (if any)
        last_a: Previous answer (if any)

    Returns:
        Rewritten standalone query, or original if no rewrite needed
    """
    if not last_q or not last_a:
        return query  # Nothing to rewrite

    prompt = (
        f"You are Steven (Hongyuan Liu). Someone asked a follow-up question.\n\n"
        f"Previous Q: \"{last_q}\"\n"
        f"Previous A: \"{last_a}\"\n"
        f"Follow-up Q: \"{query}\"\n\n"
        f"If the follow-up is related, rewrite it as a standalone question (max 20 words, no extra text). "
        f"If unrelated, just return the follow-up question as-is."
    )

    try:
        response = await openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You're a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_completion_tokens=64,
        )
        rewritten = response.choices[0].message.content.strip()
        logger.info(f"Rewrote follow-up: '{query}' -> '{rewritten}'")
        return rewritten
    except Exception as e:
        logger.warning(f"Follow-up rewrite failed: {e}, using original query")
        return query


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    _: None = Depends(verify_api_key)
):
    """
    Stream chat completion with RAG.

    Process:
    1. Retrieve RAG contexts (if enabled)
    2. Augment system message with contexts
    3. Health check GPU service (if using Qwen/Llama)
    4. Stream response with character buffering
    5. Send final complete text
    """
    logger.info(
        f"Chat request: model={request.model}, query={request.query[:50]}..., "
        f"RAG=(docs={request.use_docs_of_fact}, qa={request.use_qa_pairs})"
    )

    # Validate model
    if request.model != "chatGPT" and request.model not in settings.GPU_MODELS:
        logger.error(f"Invalid model requested: {request.model}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {request.model}. Supported: 'chatGPT' or {settings.GPU_MODELS}"
        )

    # Step 1: Rewrite follow-up questions and retrieve RAG contexts
    contexts = []
    rewritten_query = await rewrite_follow_up(request.query, request.last_q, request.last_a)

    if request.use_docs_of_fact or request.use_qa_pairs:
        # Use rewritten query for RAG search
        raw_contexts = rag_service.search(
            query=rewritten_query,
            use_docs=request.use_docs_of_fact,
            use_qa=request.use_qa_pairs
        )

        contexts = [
            RAGContext(
                content=ctx["content"],
                score=ctx["score"],
                metadata=ctx["metadata"]
            )
            for ctx in raw_contexts
        ]
        logger.info(f"Retrieved {len(contexts)} RAG contexts")

    # Step 2: Build messages for model
    messages = []
    query_for_prompt = rewritten_query

    if contexts:
        # Format context without scores (cleaner for LLM)
        context_text = "\n\n".join([ctx.content for ctx in contexts])

        # Use the proven system prompt format
        system_prompt = (
            "You are Steven (Hongyuan Liu). "
            "You're here to help people understand your work, background, projects, and experiences. "
            "If a question isn't about you, or the info retrieved doesn't help, just say you can't answer or that it's outside your knowledge."
        )

        # Format full user prompt with context (using rewritten query)
        user_prompt = (
            f'Someone asked you: "{query_for_prompt}"\n\n'
            f"To help answer, we've retrieved the following relevant information from your background:\n\n"
            f"{context_text}\n\n"
            f"Based on this, please reply naturally as yourself."
        )

        # Build messages with RAG context
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    else:
        # No RAG context - simple query
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query_for_prompt}
        ]

    # Step 3: Health check GPU service if needed
    if request.model != "chatGPT":
        logger.info("Checking GPU service health...")
        is_healthy = await gpu_client.check_health()
        if not is_healthy:
            logger.error("GPU service is not available")
            raise HTTPException(
                status_code=503,
                detail="GPU service is not available"
            )

    # Step 4: Stream response
    async def event_generator():
        try:
            # Send RAG contexts first
            if contexts:
                yield ChatResponseChunk(
                    type=ChatChunkType.CONTEXT,
                    contexts=contexts
                ).model_dump_json()

            # Stream model response with buffering
            stream_buffer = StreamBuffer()
            full_text = []

            raw_stream = model_router.route_chat_stream(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            buffered_stream = stream_buffer.buffer_stream(raw_stream)

            async for chunk_text in buffered_stream:
                if chunk_text:
                    full_text.append(chunk_text)
                    yield ChatResponseChunk(
                        type=ChatChunkType.DELTA,
                        delta=chunk_text
                    ).model_dump_json()

            # Send final complete text
            complete_text = "".join(full_text)
            yield ChatResponseChunk(
                type=ChatChunkType.DONE,
                full_text=complete_text
            ).model_dump_json()

            logger.info(f"Chat completed: {len(complete_text)} characters")

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield ChatResponseChunk(
                type=ChatChunkType.ERROR,
                error=str(e)
            ).model_dump_json()

    return EventSourceResponse(event_generator())
