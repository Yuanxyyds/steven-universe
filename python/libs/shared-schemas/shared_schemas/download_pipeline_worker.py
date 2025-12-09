"""
Download Pipeline Worker Schemas

Shared schemas for GPU service <-> download-pipeline-worker communication.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Request/Response
# ============================================================================

class DownloadPipelineTaskRequest(BaseModel):
    """
    Task request sent from GPU service to download-pipeline worker.

    Sent via: POST /task
    """
    task_id: str = Field(..., description="Unique task identifier")
    model_id: str = Field(..., description="Model identifier")
    task_preset: str = Field(..., description="Task preset name")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific parameters"
    )


class DownloadPipelineHealthResponse(BaseModel):
    """
    Worker health check response.

    Returned from: GET /health
    """
    status: str = Field(..., description="Health status: healthy, unhealthy")
    worker: str = Field(..., description="Worker name")
    model_path: str = Field(..., description="Base model path")


class DownloadPipelineStatusResponse(BaseModel):
    """
    Worker detailed status response.

    Returned from: GET /status
    """
    status: str = Field(..., description="Worker status: ready, busy")
    worker: str = Field(..., description="Worker name")
    model_path: str = Field(..., description="Model path")
    model_path_exists: bool = Field(..., description="Whether model path exists")
    total_files: int = Field(..., description="Total files in model path")
