"""
Task request handler with pipeline execution.
"""

import uuid
import logging
from typing import Dict, Any, AsyncIterator, Optional

from fastapi import HTTPException

from app.core.instance.config_loader import ConfigLoader, TaskDefinition, TaskAction, ModelPath
from app.core.instance.instance_manager import InstanceManager
from app.core.manager.model_downloader import model_downloader
from app.core.manager.task_manager import task_manager
from app.models.events import StreamEvent
from shared_schemas.gpu_service import TaskType

logger = logging.getLogger(__name__)


class TaskRequestHandler:
    """
    Handles complete execution pipeline for a single task request.

    Pipeline:
    0. Simple endpoint creates handler and calls execute()
    1. Load config (ConfigLoader instance per-request)
    1.5. Check if session type (TODO - raise NotImplementedError for now)
    2. Prepare model (ModelDownloader singleton, only if model_path provided)
    3. Allocate GPU (TaskManager.gpu_manager singleton)
    4. Create instance manager (InstanceManager instance per-request)
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
        self.model_path_config: Optional[ModelPath] = None
        self.model_host_path: Optional[str] = None
        self.gpu_id: Optional[int] = None
        self.container_id: Optional[str] = None
        self.instance_mgr: Optional[InstanceManager] = None

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

            # Step 1.5: Check if session type (TODO - skip for now)
            if self.task_def.task_type == TaskType.SESSION.value:
                raise NotImplementedError(
                    "Session tasks not yet implemented in new pipeline. "
                    "Use task_type='oneoff' for now."
                )

            # Step 2: Prepare model (only if model_path provided)
            logger.info(f"[{self.task_id}] Step 2: Preparing model")
            await self._prepare_model()

            # Step 3: Allocate GPU
            logger.info(f"[{self.task_id}] Step 3: Allocating GPU (difficulty={self.task_def.task_difficulty})")
            await self._allocate_gpu()

            # Emit CONNECTION event
            yield StreamEvent.connection(
                status="allocated",
                gpu_id=self.gpu_id,
                session_id=None
            )

            # Step 5: Create Docker container
            logger.info(f"[{self.task_id}] Step 5: Creating Docker container")
            await self._create_container()

            # Step 4: Create instance manager (after container exists)
            logger.info(f"[{self.task_id}] Step 4: Creating instance manager")
            await self._create_instance_manager()

            # Step 6: Register with task manager
            logger.info(f"[{self.task_id}] Step 6: Registering task with TaskManager")
            await task_manager.register_task(self.task_id, self.instance_mgr)

            # Step 7: Stream execution
            logger.info(f"[{self.task_id}] Step 7: Streaming task execution")

            async for event in self.instance_mgr.stream_task_execution(session_id=None):
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
        Step 1: Load configuration.

        Loads task definition, task action, and optional model path from YAML configs.
        Applies request overrides to task definition.
        """
        try:
            self.task_def, self.task_action, self.model_path_config = \
                self.config_loader.load_task_config(self.task_name)

            # Apply overrides
            if self.request_overrides.get('task_difficulty'):
                self.task_def.task_difficulty = self.request_overrides['task_difficulty']
            if self.request_overrides.get('timeout_seconds'):
                self.task_def.timeout_seconds = self.request_overrides['timeout_seconds']

            # Merge metadata
            self.task_def.metadata = {
                **self.task_def.metadata,
                **self.request_overrides.get('metadata', {})
            }

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

        Only downloads model if model_path is provided in config.
        Uses ModelDownloader singleton.
        """
        if not self.model_path_config:
            logger.info(f"[{self.task_id}] No model_path configured, skipping model preparation")
            self.model_host_path = None
            return

        # Check if model exists, download if needed
        import httpx
        async with httpx.AsyncClient() as client:
            self.model_host_path = await model_downloader.get_model_path(
                model_id=self.model_path_config.model_id,
                http_client=client
            )

        if not self.model_host_path:
            raise HTTPException(
                status_code=500,
                detail=f"Model {self.model_path_config.model_id} not available and fetch failed"
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

    async def _create_instance_manager(self):
        """
        Step 4: Create instance manager.

        Creates per-request instance manager to track worker and stream logs.
        """
        self.instance_mgr = InstanceManager(
            task_id=self.task_id,
            container_id=self.container_id,
            timeout_seconds=self.task_def.timeout_seconds
        )

        logger.info(f"[{self.task_id}] Instance manager created")

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
