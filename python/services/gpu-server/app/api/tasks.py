"""
Task submission and execution endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import verify_api_key
from shared_schemas.gpu_service import (
    PreDefinedTaskRequest,
    CustomTaskRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/tasks/predefined")
async def run_predefined_task(request: PreDefinedTaskRequest):
    """
    Execute a pre-defined task with SSE streaming.

    Routes to appropriate handler based on task_type:
    - oneoff: OneOffTaskRequestHandler
    - session: SessionTaskHandler

    Args:
        request: Pre-defined task request

    Returns:
        EventSourceResponse with SSE stream

    Raises:
        HTTPException: 404 if task not found, 503 if no resources available
    """
    from app.core.instance.config_loader import ConfigLoader
    from app.core.instance.oneoff_task_request_handler import OneOffTaskRequestHandler
    from app.core.instance.session_task_handler import SessionTaskHandler

    logger.info(f"Pre-defined task submission: task_name={request.task_name}")

    # Load config to determine task type
    config_loader = ConfigLoader()
    try:
        task_def, _, _ = config_loader.load_task_config(request.task_name)
    except Exception as e:
        logger.error(f"Failed to load task config: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Task '{request.task_name}' not found"
        )

    # Route based on task type
    if task_def.task_type == "session":
        # Session task - use SessionTaskHandler
        handler = SessionTaskHandler(
            task_name=request.task_name,
            request_overrides={
                'task_difficulty': request.task_difficulty,
                'timeout_seconds': request.timeout_seconds,
                'metadata': request.metadata,
            }
        )
    else:
        # OneOff task - use OneOffTaskRequestHandler
        handler = OneOffTaskRequestHandler(
            task_name=request.task_name,
            request_overrides={
                'task_difficulty': request.task_difficulty,
                'timeout_seconds': request.timeout_seconds,
                'metadata': request.metadata,
            }
        )

    # Execute pipeline and stream
    return EventSourceResponse(handler.execute())


@router.post("/tasks/custom")
async def run_custom_task(_request: CustomTaskRequest):
    """
    Execute a custom task (TODO).

    Placeholder for future custom task implementation where users can specify
    arbitrary docker images, commands, and configurations.

    Args:
        request: Custom task request

    Raises:
        HTTPException: 501 Not Implemented
    """
    raise HTTPException(
        status_code=501,
        detail="Custom tasks not yet implemented"
    )
