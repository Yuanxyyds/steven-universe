#!/usr/bin/env python3
"""
Download Pipeline Worker - Session-based test worker for GPU Service

Demonstrates:
- Model download pipeline (checks /data/models, downloads if missing)
- HTTP server with FastAPI (instead of docker log following)
- File enumeration and streaming responses
- SSE event format
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

# Import shared schemas
from shared_schemas.download_pipeline_worker import (
    DownloadPipelineTaskRequest,
    DownloadPipelineHealthResponse,
    DownloadPipelineStatusResponse
)

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
MODEL_PATH = os.environ.get("MODEL_PATH", "/models")

logger.info(f"Worker Configuration:")
logger.info(f"  SERVER_PORT: {SERVER_PORT}")
logger.info(f"  MODEL_PATH: {MODEL_PATH}")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(title="Download Pipeline Worker")


# ============================================================================
# Event Emission
# ============================================================================

def emit_sse_event(event_type: str, data: dict) -> str:
    """
    Format SSE event.

    Args:
        event_type: Event type (connected, logs, text_delta, text, completed)
        data: Event data

    Returns:
        SSE-formatted string
    """
    import json
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ============================================================================
# Task Processing
# ============================================================================

async def process_task(task: DownloadPipelineTaskRequest) -> AsyncIterator[str]:
    """
    Process task: enumerate model files and stream responses.

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
        logger.info(f"Processing task {task.task_id} for model {task.model_id}")

        # Log: Task received
        yield emit_sse_event("logs", {
            "log": f"Task {task.task_id} received",
            "level": "info"
        })

        # Text delta: Task Received!
        yield emit_sse_event("text_delta", {"delta": "Task Received!\n"})
        await asyncio.sleep(5)

        # Check model path
        model_path = Path(MODEL_PATH) / task.model_id

        if not model_path.exists():
            # Model not found - should have been downloaded by GPU service
            error_msg = f"Model path {model_path} does not exist"
            logger.error(error_msg)

            yield emit_sse_event("completed", {
                "status": "failed",
                "error": error_msg
            })
        else:
            # Text delta: Found folder
            yield emit_sse_event("text_delta", {"delta": "Found file's folder\n"})
            await asyncio.sleep(5)

        # Countdown from 20 to 1
        countdown_count = 0
        for count in range(20, 0, -1):
            countdown_count += 1
            yield emit_sse_event("text_delta", {
                "delta": f"Counting down: {count}\n"
            })
            await asyncio.sleep(1)

        # Text delta: Completed message
        yield emit_sse_event("text_delta", {"delta": "Completed\n"})

        # Completed event
        yield emit_sse_event("completed", {
            "status": "completed",
            "countdown_steps": countdown_count
        })

        logger.info(f"Task {task.task_id} completed successfully ({countdown_count} countdown steps)")

    except Exception as e:
        logger.error(f"Error processing task {task.task_id}: {e}", exc_info=True)
        yield emit_sse_event("completed", {
            "status": "failed",
            "error": str(e)
        })


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health", response_model=DownloadPipelineHealthResponse)
async def health():
    """Health check endpoint."""
    return DownloadPipelineHealthResponse(
        status="healthy",
        worker="download-pipeline-worker",
        model_path=MODEL_PATH
    )


@app.get("/status", response_model=DownloadPipelineStatusResponse)
async def status():
    """Worker status endpoint."""
    model_path = Path(MODEL_PATH)

    # Count files in model path
    file_count = 0
    if model_path.exists():
        for _ in model_path.rglob("*"):
            file_count += 1

    return DownloadPipelineStatusResponse(
        status="ready",
        worker="download-pipeline-worker",
        model_path=str(model_path),
        model_path_exists=model_path.exists(),
        total_files=file_count
    )


@app.post("/task")
async def submit_task(task: DownloadPipelineTaskRequest):
    """
    Submit task for processing with SSE streaming.

    Args:
        task: Task request

    Returns:
        StreamingResponse with SSE events
    """
    logger.info(f"Task endpoint called: {task.task_id}")

    return StreamingResponse(
        process_task(task),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting Download Pipeline Worker on port {SERVER_PORT}...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVER_PORT,
        log_level="info"
    )
