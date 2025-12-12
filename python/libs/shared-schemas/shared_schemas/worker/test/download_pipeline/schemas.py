"""
Download Pipeline Test Worker Schemas

Shared schemas for GPU service <-> download-pipeline test worker communication.

Note: Health and stop endpoints use shared protocol schemas from worker.protocol
"""

from typing import Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Task Request/Response (Worker-Specific)
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


# ============================================================================
# Status Response (Worker-Specific, Optional)
# ============================================================================

class DownloadPipelineStatusResponse(BaseModel):
    """
    Worker detailed status response (worker-specific).

    Returned from: GET /status
    """
    status: str = Field(..., description="Worker status: ready, busy")
    worker: str = Field(..., description="Worker name")
    model_path: str = Field(..., description="Model path")
    model_path_exists: bool = Field(..., description="Whether model path exists")
    total_files: int = Field(..., description="Total files in model path")
