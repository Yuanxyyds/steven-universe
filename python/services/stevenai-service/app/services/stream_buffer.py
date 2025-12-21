"""
Stream Buffer - Buffers characters before sending SSE deltas.

Buffers at least STREAM_BUFFER_SIZE characters before flushing to reduce SSE overhead.
"""

import asyncio
import logging
from typing import AsyncIterator

from app.core.config import settings

logger = logging.getLogger(__name__)


class StreamBuffer:
    """
    Buffers characters and flushes when:
    1. Buffer reaches STREAM_BUFFER_SIZE characters
    2. Stream ends
    """

    def __init__(
        self,
        buffer_size: int = None,
        flush_timeout: float = None
    ):
        self.buffer_size = buffer_size or settings.STREAM_BUFFER_SIZE
        self.flush_timeout = flush_timeout or settings.STREAM_FLUSH_TIMEOUT
        self.buffer = []

    async def buffer_stream(
        self,
        stream: AsyncIterator[str]
    ) -> AsyncIterator[str]:
        """
        Buffer incoming stream and yield in chunks.

        Args:
            stream: Async iterator of character deltas

        Yields:
            Buffered text chunks (buffer_size+ characters)
        """
        async for delta in stream:
            if not delta:
                continue

            self.buffer.append(delta)
            buffer_len = sum(len(s) for s in self.buffer)

            # Check if we should flush
            should_flush = buffer_len >= self.buffer_size

            if should_flush:
                yield await self._flush()

        # Flush remaining buffer at end of stream
        if self.buffer:
            yield await self._flush()

    async def _flush(self) -> str:
        """Flush buffer and return combined text."""
        if not self.buffer:
            return ""

        text = "".join(self.buffer)
        self.buffer = []

        return text
