"""
Loading Test Worker schemas.

Note: Health and stop responses use shared protocol.WorkerHealthResponse and protocol.WorkerStopResponse
"""

from shared_schemas.worker.test.loading.schemas import (
    LoadingTestTaskRequest,
    LoadingTestStatusResponse,
)

__all__ = [
    "LoadingTestTaskRequest",
    "LoadingTestStatusResponse",
]
