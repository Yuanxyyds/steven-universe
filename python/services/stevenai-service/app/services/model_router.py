"""
Model Router - Routes requests to OpenAI or GPU service.
"""

import logging
from typing import AsyncIterator, List, Dict, Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.clients.gpu_client import gpu_client

logger = logging.getLogger(__name__)


class ModelRouter:
    """Routes chat requests to appropriate model backend."""

    def __init__(self):
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )

    async def route_chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 512
    ) -> AsyncIterator[str]:
        """
        Route chat request and stream response.

        Args:
            messages: OpenAI-style messages
            model: "chatGPT" for OpenAI, or exact GPU model ID
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Yields:
            Text deltas (character-level chunks)
        """
        logger.info(f"Routing chat to model: {model}")

        if model == "chatGPT":
            async for delta in self._stream_openai(messages, max_tokens):
                yield delta
        else:
            # Assume it's a GPU model ID - pass directly to GPU service
            async for delta in self._stream_gpu(messages, model, temperature, max_tokens):
                yield delta

    async def _stream_openai(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int
    ) -> AsyncIterator[str]:
        """Stream from OpenAI API."""
        logger.info(f"Streaming from OpenAI: model={settings.OPENAI_MODEL}, max_tokens={max_tokens}")

        try:
            stream = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                max_completion_tokens=max_tokens,
                stream=True
            )

            chunk_count = 0
            total_chars = 0
            async for chunk in stream:
                chunk_count += 1
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_chars += len(content)
                    yield content
                elif chunk.choices:
                    logger.debug(f"OpenAI chunk {chunk_count}: no content, finish_reason={chunk.choices[0].finish_reason}")

            logger.info(f"OpenAI stream completed: {chunk_count} total chunks, {total_chars} total chars")

        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}", exc_info=True)
            raise

    async def _stream_gpu(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[str]:
        """Stream from GPU service using exact model ID."""
        logger.info(f"Streaming from GPU service: model_id={model_id}")

        async for delta in gpu_client.stream_chat(
            messages=messages,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            yield delta


# Global instance
model_router = ModelRouter()
