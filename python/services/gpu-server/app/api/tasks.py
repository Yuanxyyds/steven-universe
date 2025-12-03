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

    Uses clean pipeline pattern with TaskRequestHandler for execution.

    Args:
        request: Pre-defined task request

    Returns:
        EventSourceResponse with SSE stream

    Raises:
        HTTPException: 404 if task not found, 503 if no resources available
    """
    from app.core.instance.task_request_handler import TaskRequestHandler

    logger.info(f"Pre-defined task submission: task_name={request.task_name}")

    # Create handler
    handler = TaskRequestHandler(
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
