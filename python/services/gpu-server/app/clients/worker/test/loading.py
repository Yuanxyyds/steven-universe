"""
Loading Test Worker Client - HTTP client for loading test worker.

Implements GPUWorkerProtocol for loading test worker communication.
"""

import json
import logging
from typing import AsyncIterator

import httpx
from httpx_sse import aconnect_sse

from app.clients.worker.base import GPUWorkerProtocol
from app.models.task import Task
from shared_schemas.sse import StreamEvent
from shared_schemas.worker.protocol import WorkerHealthResponse, WorkerStopResponse
from shared_schemas.worker.test.loading.schemas import LoadingTestTaskRequest

logger = logging.getLogger(__name__)


class LoadingTestClient(GPUWorkerProtocol):
    """
    Client for communicating with loading test worker containers.

    Implements standardized GPUWorkerProtocol interface.
    """

    def _get_container_url(self, container_id: str, endpoint: str) -> str:
        """Build container URL for endpoint."""
        container_name = f"gpu-session-{container_id[:12]}"
        return f"http://{container_name}:8000{endpoint}"

    async def health(self, container_id: str) -> bool:
        """Check if worker is healthy."""
        health_url = self._get_container_url(container_id, "/health")

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(health_url)

                if response.status_code == 200:
                    # Parse and validate response using Pydantic schema
                    health_response = WorkerHealthResponse.model_validate_json(response.text)
                    return health_response.status == "healthy"
                return False

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking health: {e}", exc_info=True)
            return False

    async def stop(self, container_id: str) -> bool:
        """Request worker to stop gracefully."""
        stop_url = self._get_container_url(container_id, "/stop")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(stop_url)

                if response.status_code == 200:
                    # Parse and validate response using Pydantic schema
                    stop_response = WorkerStopResponse.model_validate_json(response.text)
                    return stop_response.status in ("stopping", "stopped")
                return False

        except Exception as e:
            logger.error(f"Error stopping worker {container_id}: {e}", exc_info=True)
            return False

    async def send_task_and_stream(
        self,
        container_id: str,
        task: Task,
        timeout_seconds: int
    ) -> AsyncIterator[StreamEvent]:
        """Send task and stream SSE responses."""
        task_url = self._get_container_url(container_id, "/task")

        # Prepare task request
        task_request = LoadingTestTaskRequest(
            task_id=task.task_id,
            model_name=task.task_definition.metadata.get("model_name", "test-model"),
            metadata=task.task_definition.metadata
        )

        logger.info(f"Sending task {task.task_id} to loading test worker: {task_url}")

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                async with aconnect_sse(
                    client,
                    'POST',
                    task_url,
                    json=task_request.model_dump()
                ) as event_source:
                    async for sse_event in event_source.aiter_sse():
                        try:
                            # Parse JSON data and deserialize to StreamEvent
                            data_dict = json.loads(sse_event.data)
                            yield StreamEvent.from_dict(data_dict)
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.warning(f"Failed to parse SSE event: {e}")

        except httpx.TimeoutException:
            logger.error(f"Worker timeout for task {task.task_id}")
            raise TimeoutError("Worker timeout")
        except Exception as e:
            logger.error(f"Error communicating with worker for task {task.task_id}: {e}", exc_info=True)
            raise

    async def wait_until_healthy(
        self,
        container_id: str,
        timeout: int = 30,
        retry_interval: float = 1.0
    ) -> bool:
        """Wait for worker to become healthy."""
        import asyncio

        container_name = f"gpu-session-{container_id[:12]}"
        logger.info(f"Waiting for {container_name} to become healthy (timeout: {timeout}s)")

        start_time = asyncio.get_event_loop().time()

        while True:
            is_healthy = await self.health(container_id)

            if is_healthy:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info(f"Container {container_name} is healthy (elapsed: {elapsed:.1f}s)")
                return True

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.error(f"Container {container_name} health check timeout after {timeout}s")
                return False

            await asyncio.sleep(retry_interval)
