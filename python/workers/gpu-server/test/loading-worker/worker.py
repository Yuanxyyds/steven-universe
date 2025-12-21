#!/usr/bin/env python3
"""
Loading Test Worker - Session-based test worker for GPU Service

Simulates loading and unloading a model from GPU memory using FastAPI HTTP server.
Streams SSE events to GPU service.
"""

import os
import asyncio
import logging
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

# Import shared schemas
from shared_schemas.worker.test.loading.schemas import LoadingTestTaskRequest
from shared_schemas.worker.protocol import WorkerHealthResponse, WorkerStopResponse
from shared_schemas.sse import StreamEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

SERVER_PORT = int(os.environ.get("SERVER_PORT", "8000"))
MODEL_NAME = os.environ.get("MODEL_NAME", "test-model")
MODEL_PATH = os.environ.get("MODEL_PATH", "/models")

logger.info(f"Worker Configuration:")
logger.info(f"  SERVER_PORT: {SERVER_PORT}")
logger.info(f"  MODEL_NAME: {MODEL_NAME}")
logger.info(f"  MODEL_PATH: {MODEL_PATH}")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(title="Loading Test Worker")


# ============================================================================
# Task Processing
# ============================================================================

async def process_task(task: LoadingTestTaskRequest) -> AsyncIterator[str]:
    """
    Process task: simulate GPU loading and computation with SSE streaming.

    Emits SSE events:
    - logs: Status messages
    - text_delta: Streaming text output
    - completed: Task completion

    Args:
        task: Task request

    Yields:
        SSE event strings
    """
    try:
        logger.info(f"Processing task {task.task_id} for model {MODEL_NAME}")

        # Log: Initializing GPU (reduced from 10s to 2s)
        yield StreamEvent.logs(
            log="Initializing GPU...",
            level="info"
        ).to_dict()
        await asyncio.sleep(2)

        # Log: Loading model (reduced from 15s to 3s total)
        yield StreamEvent.logs(
            log=f"Loading model {MODEL_NAME} into GPU memory...",
            level="info"
        ).to_dict()

        # Simulate loading progress (3 iterations instead of 5, 1s each instead of 3s)
        for i in range(1, 4):
            await asyncio.sleep(1)
            yield StreamEvent.text_delta(
                delta=f"Loading progress: {i * 33}%\n"
            ).to_dict()

        # Model loaded
        yield StreamEvent.logs(
            log="Model loaded successfully",
            level="info"
        ).to_dict()

        # Simulate GPU computation (reduced from 2s to 1s)
        yield StreamEvent.text_delta(
            delta="\nPerforming GPU computation...\n"
        ).to_dict()
        await asyncio.sleep(1)

        yield StreamEvent.text_delta(
            delta=f"Model {MODEL_NAME} computation complete!\nGPU memory allocated: ~2GB\n"
        ).to_dict()

        # Simulate unloading model (1s, unchanged)
        yield StreamEvent.logs(
            log="Unloading model from GPU...",
            level="info"
        ).to_dict()
        await asyncio.sleep(1)

        yield StreamEvent.text_delta(
            delta="GPU memory freed.\n"
        ).to_dict()

        # Completed event
        yield StreamEvent.completed(
            status="completed",
            model=MODEL_NAME
        ).to_dict()

        logger.info(f"Task {task.task_id} completed successfully")

    except Exception as e:
        logger.error(f"Error processing task {task.task_id}: {e}", exc_info=True)
        yield StreamEvent.completed(
            status="failed",
            error=str(e)
        ).to_dict()


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health", response_model=WorkerHealthResponse)
async def health():
    """Health check endpoint."""
    return WorkerHealthResponse(status="healthy")


@app.post("/stop", response_model=WorkerStopResponse)
async def stop():
    """
    Stop current task execution gracefully (async, returns immediately).

    Returns 200 immediately while task stops in background.
    """
    logger.info("Stop signal received, stopping current task...")
    # TODO: Implement task cancellation logic
    # For now, just return stopping status
    return WorkerStopResponse(status="stopping")


@app.post("/task")
async def submit_task(task: LoadingTestTaskRequest):
    """
    Submit task for processing with SSE streaming.

    Args:
        task: Task request

    Returns:
        StreamingResponse with SSE events
    """
    logger.info(f"Task endpoint called: {task.task_id}")

    return EventSourceResponse(process_task(task), headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    })


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting Loading Test Worker on port {SERVER_PORT}...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVER_PORT,
        log_level="info"
    )
