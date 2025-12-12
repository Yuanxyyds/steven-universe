"""
Loading Test Worker Schemas

Shared schemas for GPU service <-> loading test worker communication.

Note: Health and stop endpoints use shared protocol schemas from worker.protocol
"""

from typing import Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Task Request/Response (Worker-Specific)
# ============================================================================

class LoadingTestTaskRequest(BaseModel):
    """
    Task request sent from GPU service to loading test worker.

    Sent via: POST /task
    """
    task_id: str = Field(..., description="Unique task identifier")
    model_name: str = Field(..., description="Model name to load")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific parameters"
    )


# ============================================================================
# Status Response (Worker-Specific, Optional)
# ============================================================================

class LoadingTestStatusResponse(BaseModel):
    """
    Worker detailed status response (worker-specific).

    Returned from: GET /status
    """
    status: str = Field(..., description="Worker status: ready, busy")
    worker: str = Field(..., description="Worker name")
    model_loaded: str = Field(..., description="Currently loaded model")
