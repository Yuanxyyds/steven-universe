"""
Session Worker Client - HTTP client for communicating with session worker containers.

Handles:
- HTTP POST requests to worker /task endpoint
- SSE event stream parsing
- Converting worker responses to StreamEvent objects
"""

import logging
import json
from typing import AsyncIterator

import httpx

from app.models.task import Task
from app.models.events import StreamEvent
from shared_schemas.download_pipeline_worker import DownloadPipelineTaskRequest

logger = logging.getLogger(__name__)


class SessionWorkerClient:
    """
    Client for communicating with session worker containers over HTTP.

    Uses Docker internal networking (container name DNS resolution).
    """

    async def send_task_and_stream(
        self,
        container_id: str,
        task: Task,
        timeout_seconds: int
    ) -> AsyncIterator[StreamEvent]:
        """
        Send task to worker and stream SSE responses.

        Args:
            container_id: Container ID (used for container DNS name)
            task: Task to send
            timeout_seconds: Request timeout

        Yields:
            StreamEvent objects parsed from worker SSE stream
        """
        container_name = f"gpu-session-{container_id[:12]}"
        task_url = f"http://{container_name}:8000/task"

        # Prepare task request
        task_request = DownloadPipelineTaskRequest(
            task_id=task.task_id,
            model_id=task.task_definition.model_id,
            task_preset=task.task_definition.task_name,
            metadata=task.task_definition.metadata
        )

        logger.info(f"Sending task {task.task_id} to worker: {task_url}")

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                async with client.stream(
                    'POST',
                    task_url,
                    json=task_request.model_dump(),
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.atext()
                        logger.error(f"Worker error for task {task.task_id}: {error_text}")
                        raise Exception(f"Worker returned status {response.status_code}: {error_text}")

                    # Stream SSE events from worker
                    event_type = None
                    async for line in response.aiter_lines():
                        if line.startswith('event: '):
                            # Parse SSE event type
                            event_type = line[7:].strip()
                        elif line.startswith('data: '):
                            # Parse SSE data
                            try:
                                data = json.loads(line[6:])

                                # Create StreamEvent from parsed SSE
                                if event_type == 'logs':
                                    yield StreamEvent.logs(
                                        log=data.get('log', ''),
                                        level=data.get('level', 'info')
                                    )
                                elif event_type == 'text_delta':
                                    yield StreamEvent.text_delta(
                                        delta=data.get('delta', '')
                                    )
                                elif event_type == 'text':
                                    yield StreamEvent.text(
                                        content=data.get('content', '')
                                    )
                                elif event_type == 'completed':
                                    yield StreamEvent.completed(
                                        status=data.get('status', 'completed'),
                                        error=data.get('error')
                                    )
                                elif event_type == 'connected':
                                    yield StreamEvent.connected(
                                        status=data.get('status', 'connected')
                                    )

                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse SSE data: {line} - {e}")

        except httpx.TimeoutException:
            logger.error(f"Worker timeout for task {task.task_id}")
            raise TimeoutError("Worker timeout")
        except Exception as e:
            logger.error(f"Error communicating with worker for task {task.task_id}: {e}", exc_info=True)
            raise


# Singleton instance
session_worker_client = SessionWorkerClient()
