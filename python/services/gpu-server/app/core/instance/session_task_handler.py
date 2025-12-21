"""
Session Task Handler - Orchestrates session-based task execution.

Handles:
- Session creation with model download
- Task queuing and processing
- HTTP communication with worker
- SSE streaming to client
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, AsyncIterator, Optional

import httpx
from fastapi import HTTPException

from app.core.instance.config_loader import ConfigLoader
from app.models.task import Task, TaskDefinition, TaskAction, ModelPath
from app.models.session import Session
from app.core.manager.model_downloader import model_downloader
from app.core.manager.session_manager import session_manager
from app.core.manager.gpu_manager import gpu_manager
from app.core.manager.docker_manager import docker_manager
from shared_schemas.gpu_service import WorkerStatus
from shared_schemas.sse import StreamEvent

logger = logging.getLogger(__name__)


class SessionTaskHandler:
    """
    Handles complete execution pipeline for session-based tasks.

    Pipeline:
    1. Load config
    2. Find or create session:
       - Download model if needed
       - Allocate GPU
       - Create container with HTTP server
       - Register with SessionManager
    3. Enqueue task to session queue
    4. Calculate queue position
    5. Process based on scheduler_type:
       - Centralized: Dequeue and send to worker one at a time
       - Distributed: Send immediately (worker manages queue)
    6. Stream SSE responses from worker
    """

    def __init__(
        self,
        task_name: str,
        request_overrides: Dict[str, Any]
    ):
        """
        Initialize session task handler.

        Args:
            task_name: Pre-defined task name
            request_overrides: Request-level overrides (difficulty, timeout, metadata)
        """
        self.task_name = task_name
        self.request_overrides = request_overrides
        self.task_id = str(uuid.uuid4())

        # Will be populated during execution
        self.task_def: Optional[TaskDefinition] = None
        self.task_action: Optional[TaskAction] = None
        self.model_path: Optional[ModelPath] = None
        self.session_id: Optional[str] = None
        self.container_id: Optional[str] = None

    async def execute(self) -> AsyncIterator[StreamEvent]:
        """
        Execute session task with SSE streaming.

        Yields:
            StreamEvent objects
        """
        try:
            # Step 1: Load config
            logger.info(f"[{self.task_id}] Step 1: Loading config for task {self.task_name}")
            await self._load_config()

            # Step 2: Find or create session
            logger.info(f"[{self.task_id}] Step 2: Finding or creating session")
            session = await self._find_or_create_session()
            await session_manager.mark_activity(session.session_id)

            if not session:
                raise HTTPException(
                    status_code=503,
                    detail="Failed to create session: no available GPUs or resources"
                )

            self.session_id = session.session_id
            self.container_id = session.container_id

            # Step 3: Create task object
            task = Task.create(
                task_definition=self.task_def,
                task_action=self.task_action,
                model_path=self.model_path,
                task_id=self.task_id,
                session_id=self.session_id
            )

            # Step 4: Enqueue task to session (creates event for dispatcher)
            logger.info(f"[{self.task_id}] Step 3: Enqueuing task to session {self.session_id}")

            task_event = await session_manager.enqueue_request(self.session_id, task)

            if not task_event:
                raise HTTPException(
                    status_code=503,
                    detail=f"Session {self.session_id} queue is full"
                )

            # Step 5: Calculate queue position
            queue_position = session.queue_size - 1  # Current task is included in queue_size

            if queue_position >= 0:
                # Emit queue position notice
                yield StreamEvent.logs(
                    log=f"Queue: {queue_position} task(s) ahead of you",
                    level="info"
                ).to_dict()

            # Step 6: Process based on scheduler type
            if self.task_def.scheduler_type == "centralized":
                # Centralized: Wait for dispatcher to dequeue, then process
                async for event in self._process_centralized(session, task, task_event):
                    yield event
            else:
                # Distributed: Wait for dispatcher to dequeue, then send immediately
                async for event in self._process_distributed(session, task, task_event):
                    yield event

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[{self.task_id}] Error executing session task: {e}", exc_info=True)
            yield StreamEvent.completed(
                status="failed",
                error=str(e)
            ).to_dict()

    async def _load_config(self):
        """Load task configuration with request overrides applied."""
        config_loader = ConfigLoader()

        try:
            self.task_def, self.task_action, self.model_path = config_loader.load_task_config(
                task_name=self.task_name,
                request_overrides=self.request_overrides
            )

            logger.info(f"[{self.task_id}] Config loaded: {self.task_def}")

        except Exception as e:
            logger.error(f"[{self.task_id}] Failed to load config: {e}")
            raise HTTPException(
                status_code=404,
                detail=f"Task '{self.task_name}' not found or invalid configuration"
            )

    async def _find_or_create_session(self):
        """Find existing session or create new one with model download."""
        # Try to find existing idle session
        existing_session = await session_manager.find_idle_session(
            model_id=self.task_def.model_id,
            predefined_task_name=self.task_name
        )

        if existing_session:
            logger.info(f"[{self.task_id}] Reusing existing session {existing_session.session_id}")
            # Mark activity when reusing session
            await session_manager.mark_activity(existing_session.session_id)
            return existing_session

        # No existing session, create new one
        logger.info(f"[{self.task_id}] Creating new session")

        # Step 2a: Download model if needed
        if self.task_def.model_id:
            logger.info(f"[{self.task_id}] Preparing model {self.task_def.model_id}")

            async with httpx.AsyncClient() as client:
                model_path = await model_downloader.get_model_path(
                    model_id=self.task_def.model_id,
                    http_client=client
                )

            if not model_path:
                raise HTTPException(
                    status_code=503,
                    detail=f"Failed to download model {self.task_def.model_id}"
                )

            logger.info(f"[{self.task_id}] Model ready at {model_path}")

        # Step 2b: Allocate GPU
        logger.info(f"[{self.task_id}] Allocating GPU (difficulty={self.task_def.task_difficulty})")
        gpu_id = await gpu_manager.allocate_gpu(self.task_def.task_difficulty, self.task_id)

        if gpu_id is None:
            raise HTTPException(
                status_code=503,
                detail="No available GPUs"
            )

        try:
            # Step 2c: Generate session ID (used for both container and session)
            session_id = str(uuid.uuid4())
            logger.info(f"[{self.task_id}] Generated session ID: {session_id}")

            # Step 2d: Create Docker container with session_id
            logger.info(f"[{self.task_id}] Creating Docker container")
            container_id = await self._create_container(gpu_id, session_id)

            # Step 2e: Register session (initially in INITIALIZING status)
            logger.info(f"[{self.task_id}] Registering session")
            session = await session_manager.create_session(
                session_id=session_id,
                container_id=container_id,
                gpu_device_id=gpu_id,
                model_id=self.task_def.model_id,
                task_difficulty=self.task_def.task_difficulty,
                predefined_task_name=self.task_name,
                scheduler_type=self.task_def.scheduler_type,
                idle_timeout_seconds=self.task_def.idle_timeout_seconds
            )

            # Step 2e: Create ready event and wait for worker to be ready
            logger.info(f"[{self.task_id}] Waiting for worker to be ready (timeout={self.task_def.startup_timeout_seconds}s)")
            ready_event = session.create_ready_event()
            await self._wait_for_worker_ready(session, ready_event, timeout=self.task_def.startup_timeout_seconds)

            # Mark session activity after successful creation
            await session_manager.mark_activity(session.session_id)

            return session

        except Exception as e:
            # Cleanup on failure
            logger.error(f"[{self.task_id}] Session creation failed, cleaning up: {e}")
            await gpu_manager.release_gpu(gpu_id)
            raise

    async def _create_container(self, gpu_id: int, session_id: str) -> str:
        """
        Create Docker container for session worker.

        Args:
            gpu_id: GPU device ID
            session_id: Pre-generated session ID (shared with session_manager)
        """
        # Determine model path (only for tasks that require models)
        if self.task_def.model_id:
            model_host_path = f"/data/models/{self.task_def.model_id}"
        else:
            # For non-LLM tasks, use empty placeholder path
            model_host_path = "/tmp/no-model"

        # Create container using docker_manager
        container_id = await docker_manager.create_session_container(
            session_id=session_id,
            gpu_id=gpu_id,
            model_id=self.task_def.model_id or "none",
            docker_image=self.task_action.docker_image,
            command=self.task_action.command,
            env_vars=self.task_action.env_vars,
            model_host_path=model_host_path,
            worker_client_path=self.task_action.worker_client_path,
            startup_timeout=self.task_def.startup_timeout_seconds,
            extra_volumes=self.task_action.extra_volumes
        )

        logger.info(f"[{self.task_id}] Container created: {container_id[:12]}")
        return container_id

    async def _wait_for_worker_ready(self, session: Session, ready_event: asyncio.Event, timeout: int = 30):
        """Wait for worker to be ready by waiting on ready event."""
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=timeout)

            # Refetch session to get updated status (docker_manager updates it)
            updated_session = await session_manager.get_session(session.session_id)
            if not updated_session:
                raise RuntimeError("Session was removed during health check")

            # Check if worker is actually ready (not killed)
            if updated_session.status == WorkerStatus.WAITING:
                logger.info(f"[{self.task_id}] Worker ready (status: {updated_session.status})")
            else:
                raise RuntimeError(
                    f"Worker health check failed (status: {updated_session.status})"
                )

        except asyncio.TimeoutError:
            # Refetch to get current status
            updated_session = await session_manager.get_session(session.session_id)
            current_status = updated_session.status if updated_session else "unknown"
            raise TimeoutError(
                f"Worker not ready after {timeout}s (current status: {current_status})"
            )

    async def _process_centralized(
        self,
        session: Session,
        task: Task,
        task_event: asyncio.Event
    ) -> AsyncIterator[StreamEvent]:
        """Process task with centralized scheduling."""
        from app.clients.worker.registry import worker_client_registry

        # Get worker client dynamically from registry
        worker_client = worker_client_registry.get_client(
            self.task_action.worker_client_path
        )

        try:
            logger.info(f"[{self.task_id}] Waiting for dispatcher to dequeue task")

            # Wait for dispatcher to signal (with timeout)
            try:
                await asyncio.wait_for(
                    task_event.wait(),
                    timeout=self.task_def.timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"[{self.task_id}] Timeout waiting for dispatch")

                # Clean up task event
                session.complete_task(task.task_id)

                yield StreamEvent.completed(
                    status="timeout",
                    error="Timeout waiting for dispatch"
                ).to_dict()
                return

            logger.info(f"[{self.task_id}] Task dequeued by dispatcher, processing")

            # Send task to worker and stream responses using dynamic client
            async for event in worker_client.send_task_and_stream(
                container_id=session.container_id,
                task=task,
                timeout_seconds=self.task_def.timeout_seconds
            ):
                yield event.to_dict()

        except Exception as e:
            logger.error(f"[{self.task_id}] Error in centralized processing: {e}", exc_info=True)
            yield StreamEvent.completed(
                status="failed",
                error=str(e)
            ).to_dict()
        finally:
            # Always cleanup: update status with stop signal, mark activity, clean event
            # Update session status back to WAITING (sends stop signal to worker)
            await session_manager.update_session_status_with_cleanup(
                session_id=session.session_id,
                new_status=WorkerStatus.WAITING,
                worker_client_path=self.task_action.worker_client_path
            )

            # Mark session activity
            await session_manager.mark_activity(session.session_id)

            # Clean up task event
            session.complete_task(task.task_id)

    async def _process_distributed(
        self,
        session: Session,
        task: Task,
        task_event: asyncio.Event
    ) -> AsyncIterator[StreamEvent]:
        """Process task with distributed scheduling."""
        from app.clients.worker.registry import worker_client_registry

        # Get worker client dynamically from registry
        worker_client = worker_client_registry.get_client(
            self.task_action.worker_client_path
        )

        # Distributed: Wait for dispatcher to dequeue, then send immediately
        # Session status stays WAITING (worker manages internal queue)

        try:
            logger.info(f"[{self.task_id}] Waiting for dispatcher to dequeue task (distributed)")

            # Wait for dispatcher to signal (with timeout)
            try:
                await asyncio.wait_for(
                    task_event.wait(),
                    timeout=self.task_def.timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"[{self.task_id}] Timeout waiting for dispatch")

                # Clean up task event
                session.complete_task(task.task_id)

                yield StreamEvent.completed(
                    status="timeout",
                    error="Timeout waiting for dispatch"
                ).to_dict()
                return

            logger.info(f"[{self.task_id}] Task dequeued by dispatcher, sending to worker")

            # Mark session activity before sending
            await session_manager.mark_activity(session.session_id)

            # Send task to worker and stream responses using dynamic client
            async for event in worker_client.send_task_and_stream(
                container_id=session.container_id,
                task=task,
                timeout_seconds=self.task_def.timeout_seconds
            ):
                yield event.to_dict()

        except Exception as e:
            logger.error(f"[{self.task_id}] Error in distributed processing: {e}", exc_info=True)
            yield StreamEvent.completed(
                status="failed",
                error=str(e)
            ).to_dict()
        finally:
            # Always cleanup: mark activity, clean event
            # Note: Status stays WAITING for distributed

            # Mark session activity
            await session_manager.mark_activity(session.session_id)

            # Clean up task event
            session.complete_task(task.task_id)

