"""
Task submission and execution endpoints.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import verify_api_key
from app.core.config import settings
from app.core.model_config import model_config_manager
from app.core.gpu_manager import gpu_manager
from app.core.session_manager import session_manager
from app.core.docker_manager import docker_manager
from app.core.instance_manager import instance_manager
from app.models.task import Task
from app.models.events import StreamEvent
from shared_schemas.gpu_service import (
    TaskSubmitRequest,
    TaskType,
    TaskStatus,
    TaskDifficulty
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


async def _fetch_model_if_needed(model_id: str) -> Optional[str]:
    """
    Ensure model exists on host, fetch from file-service if needed.

    Args:
        model_id: Model identifier

    Returns:
        Host path to model directory, or None if fetch failed
    """
    import os
    import httpx

    # Check if model exists in cache
    model_cache_dir = settings.MODEL_CACHE_DIR
    model_host_path = os.path.join(model_cache_dir, model_id)

    if os.path.exists(model_host_path):
        logger.info(f"Model {model_id} found in cache at {model_host_path}")
        return model_host_path

    # Auto-fetch disabled
    if not settings.AUTO_FETCH_MODELS:
        logger.warning(f"Model {model_id} not found and AUTO_FETCH_MODELS=false")
        return None

    # Fetch from file-service
    logger.info(f"Model {model_id} not found, fetching from file-service...")

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{settings.FILE_SERVICE_URL}/api/models/download",
                json={"model_id": model_id, "destination": model_host_path},
                headers={"X-Internal-Key": settings.FILE_SERVICE_INTERNAL_KEY}
            )
            response.raise_for_status()

            logger.info(f"Model {model_id} fetched successfully to {model_host_path}")
            return model_host_path

    except Exception as e:
        logger.error(f"Failed to fetch model {model_id}: {e}", exc_info=True)
        return None


async def _create_task_from_request(request: TaskSubmitRequest) -> Task:
    """
    Create Task object from TaskSubmitRequest.

    Args:
        request: Task submission request

    Returns:
        Task object with generated task_id
    """
    task_id = str(uuid.uuid4())

    return Task(
        task_id=task_id,
        task_type=request.task_type,
        task_difficulty=request.task_difficulty,
        model_id=request.model_id,
        task_preset=request.task_preset,
        metadata=request.metadata,
        status=TaskStatus.PENDING,
        timeout_seconds=request.timeout_seconds
    )


async def _handle_oneoff_task(task: Task):
    """
    Handle one-off task execution (ephemeral container).

    Args:
        task: Task to execute

    Yields:
        StreamEvent objects via SSE
    """
    logger.info(f"Handling one-off task {task.task_id}")

    # Get model preset configuration
    preset = model_config_manager.get_preset(task.model_id, task.task_preset)
    if not preset:
        raise HTTPException(
            status_code=400,
            detail=f"No preset found for model_id={task.model_id}, task_preset={task.task_preset}"
        )

    # Fetch model if needed
    model_host_path = await _fetch_model_if_needed(task.model_id)
    if not model_host_path:
        raise HTTPException(
            status_code=500,
            detail=f"Model {task.model_id} not available and fetch failed"
        )

    # Allocate GPU
    gpu_device_id = await gpu_manager.allocate_gpu(task.task_difficulty, task.task_id)
    if gpu_device_id is None:
        raise HTTPException(
            status_code=503,
            detail=f"No available GPU with difficulty={task.task_difficulty}"
        )

    try:
        # Emit CONNECTION event
        yield StreamEvent.connection(
            status="allocated",
            gpu_id=gpu_device_id,
            session_id=None
        )

        # Create one-off container
        container_id = await docker_manager.create_oneoff_container(
            task_id=task.task_id,
            gpu_id=gpu_device_id,
            model_id=task.model_id,
            docker_image=preset.docker_image,
            command=preset.command,
            env_vars=preset.env_vars,
            model_host_path=model_host_path,
            metadata=task.metadata
        )

        logger.info(f"Created one-off container {container_id[:12]} for task {task.task_id}")

        # Stream task execution
        async for event in instance_manager.stream_task_execution(
            task=task,
            container_id=container_id,
            session_id=None
        ):
            yield event

    finally:
        # Release GPU
        await gpu_manager.release_gpu(gpu_device_id, task.task_id)
        logger.info(f"Released GPU {gpu_device_id} for task {task.task_id}")


async def _handle_session_task(task: Task, request: TaskSubmitRequest):
    """
    Handle session-based task execution (reuse or create session).

    Args:
        task: Task to execute
        request: Original request with session parameters

    Yields:
        StreamEvent objects via SSE
    """
    logger.info(f"Handling session task {task.task_id}")

    session = None
    session_id = request.session_id

    # Get model preset configuration
    preset = model_config_manager.get_preset(task.model_id, task.task_preset)
    if not preset:
        raise HTTPException(
            status_code=400,
            detail=f"No preset found for model_id={task.model_id}, task_preset={task.task_preset}"
        )

    # Fetch model if needed
    model_host_path = await _fetch_model_if_needed(task.model_id)
    if not model_host_path:
        raise HTTPException(
            status_code=500,
            detail=f"Model {task.model_id} not available and fetch failed"
        )

    # Case 1: Reuse existing session
    if session_id:
        session = await session_manager.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        if session.model_id != task.model_id:
            raise HTTPException(
                status_code=400,
                detail=f"Session {session_id} has model {session.model_id}, but task requires {task.model_id}"
            )

        # Try to enqueue request
        enqueued = await session_manager.enqueue_request(session_id, task)
        if not enqueued:
            raise HTTPException(
                status_code=503,
                detail=f"Session {session_id} queue is full"
            )

        logger.info(f"Enqueued task {task.task_id} to existing session {session_id}")

    # Case 2: Create new session OR find idle session with same model
    else:
        # Try to find idle session with same model
        if not request.create_session:
            session = await session_manager.find_idle_session_with_model(task.model_id)

            if session:
                logger.info(f"Found idle session {session.session_id} with model {task.model_id}")
                session_id = session.session_id

                # Enqueue request
                enqueued = await session_manager.enqueue_request(session_id, task)
                if not enqueued:
                    # Queue full, fall through to create new session
                    logger.warning(f"Idle session {session_id} queue full, creating new session")
                    session = None

        # Create new session if no idle session found or create_session=True
        if not session:
            # Allocate GPU
            gpu_device_id = await gpu_manager.allocate_gpu(task.task_difficulty, task.task_id)
            if gpu_device_id is None:
                raise HTTPException(
                    status_code=503,
                    detail=f"No available GPU with difficulty={task.task_difficulty}"
                )

            try:
                # Create session container
                container_id = await docker_manager.create_session_container(
                    session_id=str(uuid.uuid4()),
                    gpu_id=gpu_device_id,
                    model_id=task.model_id,
                    docker_image=preset.docker_image,
                    command=preset.command,
                    env_vars=preset.env_vars,
                    model_host_path=model_host_path
                )

                logger.info(f"Created session container {container_id[:12]}")

                # Create session in manager
                session = await session_manager.create_session(
                    container_id=container_id,
                    gpu_device_id=gpu_device_id,
                    model_id=task.model_id,
                    task_difficulty=task.task_difficulty
                )
                session_id = session.session_id

                # Enqueue first request
                await session_manager.enqueue_request(session_id, task)

                logger.info(f"Created new session {session_id}")

            except Exception as e:
                # Release GPU on failure
                await gpu_manager.release_gpu(gpu_device_id, task.task_id)
                raise

    # Emit CONNECTION event
    yield StreamEvent.connection(
        status="session_ready",
        gpu_id=session.gpu_device_id,
        session_id=session_id
    )

    # Stream task execution from session container
    async for event in instance_manager.stream_task_execution(
        task=task,
        container_id=session.container_id,
        session_id=session_id
    ):
        yield event


@router.post("/tasks/submit")
async def submit_task(
    request_obj: Request,
    request: TaskSubmitRequest
):
    """
    Submit task for execution with SSE streaming.

    Args:
        request: Task submission request

    Returns:
        EventSourceResponse with SSE stream

    Raises:
        HTTPException: 400 if invalid request, 503 if no resources available
    """
    logger.info(f"Task submission: type={request.task_type}, model={request.model_id}, preset={request.task_preset}")

    # Validate timeout
    if request.timeout_seconds > settings.MAX_TASK_TIMEOUT:
        raise HTTPException(
            status_code=400,
            detail=f"Timeout exceeds maximum ({settings.MAX_TASK_TIMEOUT}s)"
        )

    # Create task object
    task = await _create_task_from_request(request)

    async def event_generator():
        """SSE event generator."""
        try:
            if request.task_type == TaskType.ONEOFF:
                async for event in _handle_oneoff_task(task):
                    yield event.to_sse_format()

            elif request.task_type == TaskType.SESSION:
                async for event in _handle_session_task(task, request):
                    yield event.to_sse_format()

            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid task_type: {request.task_type}"
                )

        except HTTPException:
            raise

        except Exception as e:
            logger.error(f"Error in task execution: {e}", exc_info=True)

            # Emit error event
            error_event = StreamEvent.task_finish(
                status="failed",
                error=str(e)
            )
            yield error_event.to_sse_format()

    return EventSourceResponse(event_generator())
