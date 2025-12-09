"""
OneOff task request handler with pipeline execution.
"""

import asyncio
import uuid
import logging
from typing import Dict, Any, AsyncIterator, Optional
from datetime import datetime

from fastapi import HTTPException

from app.core.instance.config_loader import ConfigLoader
from app.models.task import Task, TaskDefinition, TaskAction
from app.core.manager.model_downloader import model_downloader
from app.core.manager.task_manager import task_manager
from app.core.manager.docker_manager import docker_manager
from app.models.events import StreamEvent, EventParser
from shared_schemas.gpu_service import TaskType

logger = logging.getLogger(__name__)


class _DockerLogStreamer:
    """
    Docker log streamer for oneoff tasks.

    Handles:
    - Streaming docker logs from oneoff containers
    - Parsing logs into structured events
    - Emitting SSE events
    - Task timeout enforcement
    """

    def __init__(self, task_id: str, container_id: str, timeout_seconds: int):
        """
        Initialize docker log streamer.

        Args:
            task_id: Task identifier
            container_id: Docker container ID
            timeout_seconds: Task timeout in seconds
        """
        self.task_id = task_id
        self.container_id = container_id
        self.timeout_seconds = timeout_seconds

    async def stream_task_execution(
        self,
        session_id: Optional[str] = None
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream task execution via docker logs parsing.

        Args:
            session_id: Optional session ID (unused for oneoff tasks)

        Yields:
            StreamEvent objects
        """
        logger.info(f"Starting log stream for task {self.task_id} (container={self.container_id[:12]})")

        task_start_time = datetime.utcnow()

        try:
            # Emit LOGS event (container created)
            yield StreamEvent.logs(
                log=f"Worker container created: {self.container_id[:12]}",
                level="info"
            )

            # Stream and parse docker logs
            log_stream = docker_manager.stream_logs(self.container_id, follow=True)

            async for log_line in log_stream:
                # Check task timeout
                elapsed = (datetime.utcnow() - task_start_time).total_seconds()
                if elapsed > self.timeout_seconds:
                    logger.warning(f"Task {self.task_id} exceeded timeout ({self.timeout_seconds}s)")

                    # Stop container
                    await docker_manager.stop_container(self.container_id)

                    # Emit timeout event
                    yield StreamEvent.completed(
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
            elapsed_seconds = int((datetime.utcnow() - task_start_time).total_seconds())

            logger.info(f"Task {self.task_id} completed successfully ({elapsed_seconds}s)")

            yield StreamEvent.completed(
                status="completed",
                elapsed_seconds=elapsed_seconds
            )

        except asyncio.CancelledError:
            logger.info(f"Task {self.task_id} stream cancelled")

            yield StreamEvent.completed(
                status="cancelled",
                error="Task cancelled"
            )
            raise

        except Exception as e:
            logger.error(f"Error streaming task {self.task_id}: {e}", exc_info=True)

            yield StreamEvent.completed(
                status="failed",
                error=str(e)
            )


class OneOffTaskRequestHandler:
    """
    Handles complete execution pipeline for a single oneoff task request.

    Pipeline:
    0. Simple endpoint creates handler and calls execute()
    1. Load config (ConfigLoader instance per-request)
    2. Prepare model (ModelDownloader singleton, only if model_path provided)
    3. Allocate GPU (TaskManager.gpu_manager singleton)
    4. Create Docker log streamer (_DockerLogStreamer instance per-request)
    5. Create Docker container (TaskManager.docker_manager singleton)
    6. Register with TaskManager (tracks running tasks)
    7. Stream execution
    """

    def __init__(
        self,
        task_name: str,
        request_overrides: Dict[str, Any]
    ):
        """
        Initialize task request handler.

        Args:
            task_name: Pre-defined task name from task_definitions.yaml
            request_overrides: Dict with optional overrides for:
                - task_difficulty
                - timeout_seconds
                - metadata
        """
        self.task_name = task_name
        self.request_overrides = request_overrides

        # Pipeline state
        self.task_id = str(uuid.uuid4())
        self.config_loader = ConfigLoader()  # Per-request instance
        self.task_def: Optional[TaskDefinition] = None
        self.task_action: Optional[TaskAction] = None
        self.model_host_path: Optional[str] = None
        self.gpu_id: Optional[int] = None
        self.container_id: Optional[str] = None
        self.log_streamer: Optional[_DockerLogStreamer] = None
        self.task: Optional[Task] = None  # Task object for tracking

    async def execute(self) -> AsyncIterator[StreamEvent]:
        """
        Execute the complete pipeline and stream events.

        Yields:
            StreamEvent objects via SSE

        Raises:
            HTTPException: On validation or resource allocation failures
        """
        try:
            # Step 1: Load config
            logger.info(f"[{self.task_id}] Step 1: Loading config for task {self.task_name}")
            await self._load_config()

            # Step 1b: Create Task object for tracking
            self.task = Task.create(
                task_definition=self.task_def,
                task_action=self.task_action,
                model_path=None,  # Will be populated after model download
                task_id=self.task_id,
                session_id=None  # Oneoff tasks don't have session_id
            )
            logger.info(f"[{self.task_id}] Task object created for tracking")

            # Step 2: Prepare model (only if model_path provided)
            logger.info(f"[{self.task_id}] Step 2: Preparing model")
            await self._prepare_model()

            # Step 3: Allocate GPU
            logger.info(f"[{self.task_id}] Step 3: Allocating GPU (difficulty={self.task_def.task_difficulty})")
            await self._allocate_gpu()

            # Emit CONNECTED event
            yield StreamEvent.connected(
                status="allocated",
                gpu_id=self.gpu_id,
                session_id=None
            )

            # Step 5: Create Docker container
            logger.info(f"[{self.task_id}] Step 5: Creating Docker container")
            await self._create_container()

            # Step 4: Create docker log streamer (after container exists)
            logger.info(f"[{self.task_id}] Step 4: Creating docker log streamer")
            await self._create_log_streamer()

            # Step 5: Update task with container_id and GPU
            self.task.container_id = self.container_id
            self.task.gpu_id = self.gpu_id

            # Step 6: Register with task manager
            logger.info(f"[{self.task_id}] Step 6: Registering task with TaskManager")
            await task_manager.register_task(self.task_id, self.task)

            # Step 7: Stream execution
            logger.info(f"[{self.task_id}] Step 7: Streaming task execution")

            async for event in self.log_streamer.stream_task_execution(session_id=None):
                yield event

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[{self.task_id}] Pipeline error: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Task execution failed: {str(e)}"
            )
        finally:
            # Cleanup
            await self._cleanup()

    async def _load_config(self):
        """
        Step 1: Load configuration with request overrides applied.

        Loads task definition and task action from YAML configs.
        ConfigLoader handles applying request overrides.
        """
        try:
            self.task_def, self.task_action, _ = \
                self.config_loader.load_task_config(
                    task_name=self.task_name,
                    request_overrides=self.request_overrides
                )

            logger.info(
                f"[{self.task_id}] Config loaded: "
                f"type={self.task_def.task_type}, "
                f"difficulty={self.task_def.task_difficulty}, "
                f"model_id={self.task_def.model_id}"
            )

        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    async def _prepare_model(self):
        """
        Step 2: Prepare model (download if needed).

        Only downloads model if model_id is provided in config.
        Uses ModelDownloader singleton.
        """
        if not self.task_def.model_id:
            logger.info(f"[{self.task_id}] No model_id configured, skipping model preparation")
            self.model_host_path = None
            return

        # Check if model exists, download if needed
        import httpx
        async with httpx.AsyncClient() as client:
            self.model_host_path = await model_downloader.get_model_path(
                model_id=self.task_def.model_id,
                http_client=client
            )

        if not self.model_host_path:
            raise HTTPException(
                status_code=500,
                detail=f"Model {self.task_def.model_id} not available and fetch failed"
            )

        logger.info(f"[{self.task_id}] Model ready at {self.model_host_path}")

    async def _allocate_gpu(self):
        """
        Step 3: Allocate GPU.

        Allocates GPU based on task difficulty using GPU Manager singleton.
        """
        self.gpu_id = await task_manager.gpu_manager.allocate_gpu(
            self.task_def.task_difficulty,
            self.task_id
        )

        if self.gpu_id is None:
            raise HTTPException(
                status_code=503,
                detail=f"No available GPU with difficulty={self.task_def.task_difficulty}"
            )

        logger.info(f"[{self.task_id}] Allocated GPU {self.gpu_id}")

    async def _create_container(self):
        """
        Step 5: Create Docker container.

        Creates one-off container using Docker Manager singleton.
        """
        # Prepare volume mounts (model path if provided)
        volume_mounts = {}
        if self.model_host_path:
            volume_mounts[self.model_host_path] = "/models"

        # Merge env vars with metadata
        env_vars = {
            **self.task_action.env_vars,
            **{f"METADATA_{k.upper()}": str(v) for k, v in self.task_def.metadata.items()}
        }
        if self.model_host_path:
            env_vars["MODEL_PATH"] = "/models"

        self.container_id = await task_manager.docker_manager.create_oneoff_container(
            task_id=self.task_id,
            gpu_id=self.gpu_id,
            docker_image=self.task_action.docker_image,
            command=self.task_action.command,
            env_vars=env_vars,
            volume_mounts=volume_mounts
        )

        logger.info(f"[{self.task_id}] Created container {self.container_id[:12]}")

    async def _create_log_streamer(self):
        """
        Step 4: Create docker log streamer.

        Creates per-request log streamer to stream docker logs and emit SSE events.
        """
        self.log_streamer = _DockerLogStreamer(
            task_id=self.task_id,
            container_id=self.container_id,
            timeout_seconds=self.task_def.timeout_seconds
        )

        logger.info(f"[{self.task_id}] Docker log streamer created")

    async def _cleanup(self):
        """
        Cleanup resources.

        Unregisters task from TaskManager and releases GPU.
        """
        logger.info(f"[{self.task_id}] Cleaning up resources")

        # Unregister from task manager
        await task_manager.unregister_task(self.task_id)

        # Release GPU
        if self.gpu_id is not None:
            await task_manager.gpu_manager.release_gpu(self.gpu_id, self.task_id)
            logger.info(f"[{self.task_id}] Released GPU {self.gpu_id}")
