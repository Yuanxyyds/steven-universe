"""
Health check endpoint.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.core.gpu_manager import gpu_manager
from app.core.session_manager import session_manager
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
