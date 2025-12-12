"""
GPU Worker Protocol - Abstract base class for all worker clients.

All worker clients must inherit from GPUWorkerProtocol and implement
the required methods for health checks, task submission, and worker shutdown.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.models.task import Task
from shared_schemas.gpu_service import StreamEvent


class GPUWorkerProtocol(ABC):
    """
    Abstract base class defining the standardized interface for GPU worker clients.

    All worker implementations must:
    1. Implement health(), stop(), send_task_and_stream(), and wait_until_healthy() methods
    2. Follow standardized endpoint contracts:
       - GET /health returns {"status": "healthy"}
       - POST /stop returns immediately (async shutdown in background)
       - POST /task accepts task and streams SSE responses
    """

    @abstractmethod
    async def health(self, container_id: str) -> bool:
        """
        Check if worker container is healthy.

        Calls: GET /health
        Expected response: {"status": "healthy"}

        Args:
            container_id: Container ID to check

        Returns:
            True if healthy (200 status + "healthy"), False otherwise
        """
        pass

    @abstractmethod
    async def stop(self, container_id: str) -> bool:
        """
        Request worker to stop gracefully.

        Calls: POST /stop
        Expected behavior: Returns 200 immediately, worker stops in background

        Args:
            container_id: Container ID to stop

        Returns:
            True if stop request accepted (200 status), False otherwise
        """
        pass

    @abstractmethod
    async def send_task_and_stream(
        self,
        container_id: str,
        task: Task,
        timeout_seconds: int
    ) -> AsyncIterator[StreamEvent]:
        """
        Send task to worker and stream SSE responses.

        Calls: POST /task with worker-specific request schema
        Expected response: SSE stream with events (logs, text_delta, completed, etc.)

        Args:
            container_id: Container ID to send task to
            task: Task object with definition, action, and metadata
            timeout_seconds: Request timeout

        Yields:
            StreamEvent objects parsed from worker SSE stream

        Raises:
            TimeoutError: If worker timeout
            Exception: If worker returns error or communication fails
        """
        pass

    @abstractmethod
    async def wait_until_healthy(
        self,
        container_id: str,
        timeout: int = 30,
        retry_interval: float = 1.0
    ) -> bool:
        """
        Wait for worker container to become healthy.

        Polls health endpoint until healthy or timeout.

        Args:
            container_id: Container ID to check
            timeout: Max seconds to wait
            retry_interval: Seconds between retries

        Returns:
            True if became healthy within timeout, False otherwise
        """
        pass
