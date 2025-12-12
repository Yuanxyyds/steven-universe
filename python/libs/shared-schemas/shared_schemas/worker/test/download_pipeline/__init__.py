"""
Download Pipeline Test Worker schemas.

Note: Health and stop responses use shared protocol.WorkerHealthResponse and protocol.WorkerStopResponse
"""

from shared_schemas.worker.test.download_pipeline.schemas import (
    DownloadPipelineTaskRequest,
    DownloadPipelineStatusResponse,
)

__all__ = [
    "DownloadPipelineTaskRequest",
    "DownloadPipelineStatusResponse",
]
