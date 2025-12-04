"""
Streaming upload utilities.
Async-to-sync bridging for boto3 uploads.
"""

import asyncio
import hashlib
import logging
from typing import AsyncIterator, Optional

from app.s3.config import MAX_BUFFERED_CHUNKS

logger = logging.getLogger(__name__)


class AsyncChunkBuffer:
    """
    Bridge async chunk iterator with sync file-like interface for boto3.
    Uses bounded queue for backpressure control.

    CRITICAL: Must be created in async context (captures event loop).
    Producer starts immediately in background.

    Features:
    - Zero-copy streaming with bounded backpressure
    - SHA256 checksum calculation for integrity verification
    - Thread-safe async/sync bridging
    """

    def __init__(self, chunk_iterator: AsyncIterator[bytes], calculate_checksum: bool = True):
        """
        Initialize buffer with async chunk iterator.

        MUST be called from async context (not from boto3 thread).

        Args:
            chunk_iterator: Async generator yielding file chunks
            calculate_checksum: Whether to calculate SHA256 checksum (default: True)
        """
        self.chunk_iterator = chunk_iterator
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_BUFFERED_CHUNKS)
        self.buffer = bytearray()
        self.finished = False
        self.error: Optional[Exception] = None

        # SHA256 checksum calculation
        self.calculate_checksum = calculate_checksum
        self.sha256 = hashlib.sha256() if calculate_checksum else None
        self.total_bytes = 0

        # CRITICAL: Capture event loop NOW (we're in async context)
        self._loop = asyncio.get_event_loop()

        # Start producer immediately
        self._producer_task = self._loop.create_task(self._produce_chunks())

    async def _produce_chunks(self):
        """Background coroutine to read from iterator and feed queue."""
        try:
            async for chunk in self.chunk_iterator:
                await self.queue.put(chunk)
            self.finished = True
            await self.queue.put(None)  # Sentinel value
        except Exception as e:
            logger.error(f"[ASYNC CHUNK BUFFER] Error in producer: {e}")
            self.error = e
            self.finished = True
            await self.queue.put(None)

    def read(self, size: int = -1) -> bytes:
        """
        Sync read interface for boto3.

        Called from boto3 worker thread. Uses run_coroutine_threadsafe
        to get chunks from async producer.

        Args:
            size: Number of bytes to read (-1 for all remaining)

        Returns:
            Bytes read from buffer/queue
        """
        # If we have buffered data and size is specified
        if size > 0 and len(self.buffer) >= size:
            data = bytes(self.buffer[:size])
            self.buffer = self.buffer[size:]

            # Update checksum and byte count
            if self.calculate_checksum and self.sha256:
                self.sha256.update(data)
            self.total_bytes += len(data)

            return data

        # Need more data - drain queue
        while True:
            # Check for errors
            if self.error:
                raise self.error

            # If finished and buffer is empty
            if self.finished and len(self.buffer) == 0:
                return b""

            # Try to get chunk from queue
            try:
                # Use run_coroutine_threadsafe since boto3 runs in thread
                future = asyncio.run_coroutine_threadsafe(
                    self.queue.get(),
                    self._loop
                )
                chunk = future.result(timeout=30)  # 30 second timeout

                if chunk is None:  # Sentinel - no more data
                    self.finished = True
                    if size == -1 or size >= len(self.buffer):
                        data = bytes(self.buffer)
                        self.buffer.clear()
                        # Update checksum for final data
                        if data and self.calculate_checksum and self.sha256:
                            self.sha256.update(data)
                        self.total_bytes += len(data)
                        return data
                    elif size > 0:
                        data = bytes(self.buffer[:size])
                        self.buffer = self.buffer[size:]
                        # Update checksum
                        if data and self.calculate_checksum and self.sha256:
                            self.sha256.update(data)
                        self.total_bytes += len(data)
                        return data
                else:
                    self.buffer.extend(chunk)

                # If we have enough data now
                if size > 0 and len(self.buffer) >= size:
                    data = bytes(self.buffer[:size])
                    self.buffer = self.buffer[size:]
                    # Update checksum
                    if self.calculate_checksum and self.sha256:
                        self.sha256.update(data)
                    self.total_bytes += len(data)
                    return data

                # If reading all (-1) and finished
                if size == -1 and self.finished:
                    data = bytes(self.buffer)
                    self.buffer.clear()
                    # Update checksum
                    if data and self.calculate_checksum and self.sha256:
                        self.sha256.update(data)
                    self.total_bytes += len(data)
                    return data

            except asyncio.TimeoutError:
                raise IOError("Timeout waiting for chunk data")
            except Exception as e:
                logger.error(f"[ASYNC CHUNK BUFFER] Read error: {e}")
                raise

    def readable(self) -> bool:
        """Required for file-like interface."""
        return True

    def seekable(self) -> bool:
        """Required for file-like interface."""
        return False

    def writable(self) -> bool:
        """Required for file-like interface."""
        return False

    def get_checksum(self) -> Optional[str]:
        """
        Get SHA256 checksum of uploaded data.

        Returns:
            Hex string of SHA256 checksum, or None if checksum not calculated
        """
        if self.sha256:
            return self.sha256.hexdigest()
        return None
