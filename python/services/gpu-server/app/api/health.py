"""
Health check endpoint.
"""

from fastapi import APIRouter
from typing import Dict, Any
from datetime import datetime

from app.core.config import settings
from app.core.manager.gpu_manager import gpu_manager
from app.core.manager.session_manager import session_manager
from app.core.manager.task_manager import task_manager
from shared_schemas.gpu_service import HealthResponse, GPUStatus

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Get service health status.

    Returns:
        HealthResponse with service status, GPU status, and session counts
    """
    # Get GPU status
    gpu_devices = await gpu_manager.get_gpu_status()

    # Convert to GPUStatus schema with difficulty mapping
    gpu_statuses = []
    for device in gpu_devices:
        difficulty = settings.GPU_DEVICE_DIFFICULTY.get(device.device_id, "low")

        gpu_status = GPUStatus(
            device_id=device.device_id,
            name=device.name,
            difficulty=difficulty,
            is_available=device.is_available,
            memory_used_mb=device.memory_used_mb,
            memory_total_mb=device.memory_total_mb,
            temperature_celsius=device.temperature_celsius,
            utilization_percent=device.utilization_percent,
            current_session_id=device.current_job_id  # Note: legacy field name
        )
        gpu_statuses.append(gpu_status)

    # Get session counts
    all_sessions = await session_manager.get_all_sessions()
    active_sessions = len(all_sessions)

    # Count active tasks (tasks currently being processed)
    active_tasks = sum(
        1 for session in all_sessions
        if session.current_task_id is not None
    )

    # Determine overall status
    status = "healthy"
    if active_sessions == 0 and len(gpu_devices) == 0:
        status = "unhealthy"
    elif all(not gpu.is_available for gpu in gpu_devices):
        status = "degraded"

    return HealthResponse(
        status=status,
        version=settings.APP_VERSION,
        gpus=gpu_statuses,
        active_sessions=active_sessions,
        active_tasks=active_tasks
    )


@router.get("/health/resources")
async def resource_allocation() -> Dict[str, Any]:
    """
    Get detailed resource allocation from TaskManager.

    Shows current GPU allocation, running tasks, and session status.

    Returns:
        Detailed resource allocation information
    """
    # Get GPU status with current allocations
    gpu_devices = await gpu_manager.get_gpu_status()

    gpu_allocation = []
    for device in gpu_devices:
        difficulty = settings.GPU_DEVICE_DIFFICULTY.get(device.device_id, "low")

        gpu_info = {
            "device_id": device.device_id,
            "name": device.name,
            "difficulty": difficulty,
            "is_available": device.is_available,
            "current_task_id": device.current_job_id,  # Task currently using this GPU
            "memory": {
                "used_mb": device.memory_used_mb,
                "total_mb": device.memory_total_mb,
                "utilization_percent": round((device.memory_used_mb / device.memory_total_mb) * 100, 2) if device.memory_total_mb > 0 else 0
            },
            "gpu_utilization_percent": device.utilization_percent,
            "temperature_celsius": device.temperature_celsius
        }
        gpu_allocation.append(gpu_info)

    # Get running tasks from TaskManager
    running_task_ids = task_manager.get_running_tasks()

    # Get session information
    all_sessions = await session_manager.get_all_sessions()

    sessions_info = []
    for session in all_sessions:
        session_info = {
            "session_id": session.session_id,
            "status": session.status.value,
            "gpu_device_id": session.gpu_device_id,
            "model_id": session.model_id,
            "current_task_id": session.current_task_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "queue_size": session.request_queue.qsize() if hasattr(session, 'request_queue') else 0
        }
        sessions_info.append(session_info)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "resource_allocation": {
            "gpus": gpu_allocation,
            "running_tasks": {
                "count": len(running_task_ids),
                "task_ids": running_task_ids
            },
            "sessions": {
                "count": len(all_sessions),
                "active": len([s for s in all_sessions if s.status.value in ["working", "initializing"]]),
                "idle": len([s for s in all_sessions if s.status.value == "waiting"]),
                "details": sessions_info
            }
        },
        "capacity": {
            "total_gpus": len(gpu_devices),
            "available_gpus": len([g for g in gpu_devices if g.is_available]),
            "gpus_by_difficulty": {
                "low": len([g for g in gpu_devices if settings.GPU_DEVICE_DIFFICULTY.get(g.device_id, "low") == "low"]),
                "high": len([g for g in gpu_devices if settings.GPU_DEVICE_DIFFICULTY.get(g.device_id, "low") == "high"])
            }
        }
    }
