"""
Instance Manager - Per-request proxy for streaming and event handling.

Handles:
- Streaming docker logs
- Parsing logs into structured events
- Emitting SSE events
- Worker status tracking
- Task timeout enforcement
"""

import asyncio
import logging
from typing import AsyncIterator, Optional
from datetime import datetime

from app.core.docker_manager import docker_manager
from app.models.events import StreamEvent, EventParser
from app.models.task import Task
from shared_schemas.gpu_service import TaskStatus

logger = logging.getLogger(__name__)


class WorkerStatus:
    """Worker status tracking (for monitoring purposes)."""
    INITIALIZING = "initializing"
    WORKING = "working"
    WAITING = "waiting"
    KILLED = "killed"


class InstanceManager:
    """
    Manages per-request execution and event streaming.

    Each task submission creates an instance that:
    1. Streams docker logs from container
    2. Parses logs into events
    3. Emits SSE events to client
    4. Enforces task timeout
    """

    def __init__(self):
        pass

    async def stream_task_execution(
        self,
        task: Task,
        container_id: str,
        session_id: Optional[str] = None
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream task execution via docker logs parsing.

        Args:
            task: Task being executed
            container_id: Docker container ID
            session_id: Optional session ID

        Yields:
            StreamEvent objects
        """
        logger.info(f"Starting log stream for task {task.task_id} (container={container_id[:12]})")

        task_start_time = datetime.utcnow()
        task.started_at = task_start_time
        task.status = TaskStatus.RUNNING

        try:
            # Emit WORKER event (container created)
            yield StreamEvent.worker(status="created", container_id=container_id)

            # Stream and parse docker logs
            log_stream = docker_manager.stream_logs(container_id, follow=True)

            async for log_line in log_stream:
                # Check task timeout
                elapsed = (datetime.utcnow() - task_start_time).total_seconds()
                if elapsed > task.timeout_seconds:
                    logger.warning(f"Task {task.task_id} exceeded timeout ({task.timeout_seconds}s)")

                    # Stop container
                    await docker_manager.stop_container(container_id)

                    # Emit timeout event
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.utcnow()
                    task.error_message = "Task timeout exceeded"

                    yield StreamEvent.task_finish(
                        status="timeout",
                        elapsed_seconds=int(elapsed),
                        error="Task timeout exceeded"
                    )
                    return

                # Parse log line into event
                event = EventParser.parse_log_line(log_line)
                if event:
                    yield event

            # Task completed successfully (container exited)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            elapsed_seconds = task.elapsed_seconds

            logger.info(f"Task {task.task_id} completed successfully ({elapsed_seconds}s)")

            yield StreamEvent.task_finish(
                status="completed",
                elapsed_seconds=elapsed_seconds
            )

        except asyncio.CancelledError:
            logger.info(f"Task {task.task_id} stream cancelled")
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error_message = "Task cancelled"

            yield StreamEvent.task_finish(
                status="cancelled",
                error="Task cancelled"
            )
            raise

        except Exception as e:
            logger.error(f"Error streaming task {task.task_id}: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error_message = str(e)

            yield StreamEvent.task_finish(
                status="failed",
                error=str(e)
            )

    async def send_command_to_container(
        self,
        container_id: str,
        command: str
    ) -> Optional[str]:
        """
        Send command to running container via docker exec.

        Args:
            container_id: Container ID
            command: Command to execute

        Returns:
            Command output, or None if failed
        """
        logger.info(f"Sending command to container {container_id[:12]}: {command}")
        return await docker_manager.execute_command_in_container(container_id, command)

    async def send_task_to_session_container(
        self,
        container_id: str,
        task: Task
    ) -> bool:
        """
        Send task to session container via stdin or exec.

        This sends the task metadata to the running worker container.
        The worker is expected to process it and output results to stdout.

        Args:
            container_id: Session container ID
            task: Task to execute

        Returns:
            True if sent successfully, False otherwise
        """
        import json

        # Prepare task payload
        payload = {
            "task_id": task.task_id,
            "model_id": task.model_id,
            "task_preset": task.task_preset,
            "metadata": task.metadata
        }

        # Send as JSON via docker exec (alternative: stdin)
        # For simplicity, using exec with a command that the worker listens for
        command = f"echo '{json.dumps(payload)}' > /tmp/task_input.json"

        result = await self.send_command_to_container(container_id, command)

        if result is not None:
            logger.info(f"Task {task.task_id} sent to container {container_id[:12]}")
            return True
        else:
            logger.error(f"Failed to send task {task.task_id} to container {container_id[:12]}")
            return False


# Global instance manager
instance_manager = InstanceManager()
