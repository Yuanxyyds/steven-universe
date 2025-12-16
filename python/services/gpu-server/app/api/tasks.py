"""
Task submission and execution endpoints.
"""

import logging

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import verify_api_key
from shared_schemas.gpu_service import PreDefinedTaskRequest

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/tasks/predefined")
async def run_predefined_task(request: PreDefinedTaskRequest):
    """
    Execute a pre-defined task with SSE streaming.

    All tasks now use SessionTaskHandler (oneoff removed).

    Args:
        request: Pre-defined task request

    Returns:
        EventSourceResponse with SSE stream

    Raises:
        HTTPException: 404 if task not found, 503 if no resources available
    """
    from app.core.instance.session_task_handler import SessionTaskHandler

    logger.info(f"Pre-defined task submission: task_name={request.task_name}")

    # All tasks now use SessionTaskHandler
    handler = SessionTaskHandler(
        task_name=request.task_name,
        request_overrides={
            'task_difficulty': request.task_difficulty,
            'timeout_seconds': request.timeout_seconds,
            'model_id': request.model_id,
            'metadata': request.metadata,
        }
    )

    # Execute pipeline and stream
    return EventSourceResponse(handler.execute())
