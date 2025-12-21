"""
vLLM Worker Client - HTTP client for vLLM worker.

Implements GPUWorkerProtocol for vLLM worker communication.
Converts Task objects into VLLMTaskRequest and streams back results.
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
from shared_schemas.worker.vllm.schemas import VLLMTaskRequest

logger = logging.getLogger(__name__)


class VLLMClient(GPUWorkerProtocol):
    """
    Client for communicating with vLLM worker containers.

    Implements standardized GPUWorkerProtocol interface for LLM inference.
    """

    def _get_container_url(self, container_id: str, endpoint: str) -> str:
        """Build container URL for endpoint."""
        container_name = f"gpu-session-{container_id[:12]}"
        return f"http://{container_name}:8000{endpoint}"

    async def health(self, container_id: str) -> bool:
        """
        Check if vLLM worker is healthy.

        Returns True only if both worker wrapper and vLLM server are ready.
        """
        health_url = self._get_container_url(container_id, "/health")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)

                if response.status_code == 200:
                    health_response = WorkerHealthResponse.model_validate_json(response.text)
                    return health_response.status == "healthy"
                return False

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking health: {e}", exc_info=True)
            return False

    async def stop(self, container_id: str) -> bool:
        """Request vLLM worker to stop gracefully."""
        stop_url = self._get_container_url(container_id, "/stop")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(stop_url)

                if response.status_code == 200:
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
        """
        Send LLM inference task and stream SSE responses.

        Converts Task to VLLMTaskRequest and streams back StreamEvents.
        """
        task_url = self._get_container_url(container_id, "/task")

        # Extract parameters from task metadata
        metadata = task.task_definition.metadata or {}

        # Prepare task request
        task_request = VLLMTaskRequest(
            task_id=task.task_id,
            model_id=task.task_definition.model_id or "Qwen/Qwen2.5-7B-Instruct",

            # Support both messages and prompt
            messages=metadata.get("messages"),
            prompt=metadata.get("prompt"),

            # Generation parameters with defaults
            temperature=metadata.get("temperature", 0.7),
            max_tokens=metadata.get("max_tokens", 512),
            top_p=metadata.get("top_p", 1.0),
            top_k=metadata.get("top_k", -1),
            stop=metadata.get("stop"),

            metadata=metadata
        )

        logger.info(f"Sending task {task.task_id} to vLLM worker: {task_url}")

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
                            logger.warning(f"Failed to parse SSE event: {e}, data: {sse_event.data[:200]}")

        except httpx.TimeoutException:
            logger.error(f"Worker timeout for task {task.task_id}")
            raise TimeoutError("Worker timeout")
        except Exception as e:
            logger.error(f"Error communicating with worker for task {task.task_id}: {e}", exc_info=True)
            raise

    async def wait_until_healthy(
        self,
        container_id: str,
        timeout: int = 180,
        retry_interval: float = 1.0
    ) -> bool:
        """
        Wait for vLLM worker to become healthy.

        Note: vLLM model loading can take 30-120 seconds, so default timeout
        is increased to 180s for production use.
        """
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
