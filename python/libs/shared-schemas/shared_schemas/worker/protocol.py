"""
GPU Worker Protocol Schemas

Standardized request/response schemas that all GPU workers must implement.

All workers must implement these endpoints:
- GET /health → WorkerHealthResponse
- POST /stop → WorkerStopResponse
"""

from pydantic import BaseModel, Field


class WorkerHealthResponse(BaseModel):
    """
    Standardized health check response.

    All workers must return this schema from GET /health endpoint.
    """
    status: str = Field(
        ...,
        description="Health status: 'healthy' or 'unhealthy'"
    )


class WorkerStopResponse(BaseModel):
    """
    Standardized stop response.

    All workers must return this schema from POST /stop endpoint.
    Returns immediately while worker stops asynchronously in background.
    """
    status: str = Field(
        ...,
        description="Stop status: 'stopping', 'stopped', or 'error'"
    )
