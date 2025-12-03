"""
Session management endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated

from app.core.dependencies import verify_api_key
from app.core.manager.session_manager import session_manager
from shared_schemas.gpu_service import SessionResponse, SessionListResponse

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """
    List all active sessions.

    Returns:
        SessionListResponse with list of active sessions
    """
    sessions = await session_manager.get_all_sessions()

    session_responses = []
    for session in sessions:
        session_response = SessionResponse(
            session_id=session.session_id,
            status=session.status,
            gpu_device_id=session.gpu_device_id,
            container_id=session.container_id,
            model_id=session.model_id,
            created_at=session.created_at,
            last_activity=session.last_activity,
            queue_size=session.queue_size
        )
        session_responses.append(session_response)

    return SessionListResponse(
        sessions=session_responses,
        total=len(session_responses)
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """
    Get session details by ID.

    Args:
        session_id: Session identifier

    Returns:
        SessionResponse with session details

    Raises:
        HTTPException: 404 if session not found
    """
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        gpu_device_id=session.gpu_device_id,
        container_id=session.container_id,
        model_id=session.model_id,
        created_at=session.created_at,
        last_activity=session.last_activity,
        queue_size=session.queue_size
    )


@router.delete("/sessions/{session_id}")
async def kill_session(session_id: str):
    """
    Kill session and release resources.

    Args:
        session_id: Session identifier

    Returns:
        Success message

    Raises:
        HTTPException: 404 if session not found
    """
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    await session_manager.kill_session(session_id, reason="manual")

    return {
        "success": True,
        "session_id": session_id,
        "message": "Session killed successfully"
    }


@router.post("/sessions/{session_id}/keepalive")
async def keepalive_session(session_id: str):
    """
    Reset session idle timeout (keepalive).

    Args:
        session_id: Session identifier

    Returns:
        Success message

    Raises:
        HTTPException: 404 if session not found
    """
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    await session_manager.mark_activity(session_id)

    return {
        "success": True,
        "session_id": session_id,
        "message": "Session keepalive updated",
        "last_activity": session.last_activity.isoformat()
    }
