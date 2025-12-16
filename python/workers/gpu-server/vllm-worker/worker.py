#!/usr/bin/env python3
"""
vLLM Worker - Session-based LLM inference worker using vLLM

Architecture:
- Worker wrapper (this file) runs on port 8000
- vLLM OpenAI API server runs on port 8001
- Worker makes HTTP requests to localhost:8001 for inference
- Streams SSE events back to GPU service
"""

import os
import logging
from typing import AsyncIterator

import uvicorn
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

# Import shared schemas
from shared_schemas.worker.vllm.schemas import VLLMTaskRequest
from shared_schemas.worker.protocol import WorkerHealthResponse, WorkerStopResponse
from shared_schemas.gpu_service import StreamEvent

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
VLLM_PORT = int(os.environ.get("VLLM_PORT", "8001"))
VLLM_BASE_URL = f"http://localhost:{VLLM_PORT}/v1"
MODEL_ID = os.environ.get("MODEL_ID", "Qwen3-4B-Instruct")
MODEL_PATH = os.environ.get("MODEL_PATH", "/models")

logger.info(f"vLLM Worker Configuration:")
logger.info(f"  SERVER_PORT: {SERVER_PORT}")
logger.info(f"  VLLM_PORT: {VLLM_PORT}")
logger.info(f"  VLLM_BASE_URL: {VLLM_BASE_URL}")
logger.info(f"  MODEL_ID: {MODEL_ID}")
logger.info(f"  MODEL_PATH: {MODEL_PATH}")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(title="vLLM Worker")


# ============================================================================
# vLLM Health Check Helper
# ============================================================================

async def check_vllm_health() -> bool:
    """
    Check if vLLM is ready by generating 1 token.

    This also warms up the generation path so first real request is fast.

    Returns:
        True if vLLM can generate tokens, False otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Generate 1 token to verify model is ready AND warm up generation
            response = await client.post(
                f"{VLLM_BASE_URL}/completions",
                json={
                    "model": MODEL_ID,
                    "prompt": "test",
                    "max_tokens": 1,
                    "temperature": 0.0
                }
            )
            return response.status_code == 200
    except Exception as e:
        logger.debug(f"vLLM health check failed: {e}")
        return False


# ============================================================================
# Task Processing
# ============================================================================

async def process_task(task: VLLMTaskRequest) -> AsyncIterator[str]:
    """
    Process LLM inference task via vLLM OpenAI API with SSE streaming.

    Flow:
    1. Check vLLM server health
    2. Prepare OpenAI-compatible request
    3. Stream response from vLLM
    4. Convert to SSE events for GPU service

    Args:
        task: Task request

    Yields:
        SSE event strings
    """
    try:
        logger.info(f"Processing task {task.task_id} for model {task.model_id}")

        # Check vLLM health
        yield StreamEvent.logs(
            log="Checking vLLM server status...",
            level="info"
        ).to_sse_format()

        if not await check_vllm_health():
            raise RuntimeError("vLLM server is not healthy")

        yield StreamEvent.logs(
            log="vLLM server ready",
            level="info"
        ).to_sse_format()

        # Prepare vLLM request
        prompt, messages = task.get_prompt_or_messages()

        # Determine endpoint and payload
        if messages:
            endpoint = f"{VLLM_BASE_URL}/chat/completions"
            payload = {
                "model": task.model_id,
                "messages": messages,
                "temperature": task.temperature,
                "max_tokens": task.max_tokens,
                "top_p": task.top_p,
                "stream": True,  # Always stream
            }
            if task.stop:
                payload["stop"] = task.stop
        else:
            endpoint = f"{VLLM_BASE_URL}/completions"
            payload = {
                "model": task.model_id,
                "prompt": prompt,
                "temperature": task.temperature,
                "max_tokens": task.max_tokens,
                "top_p": task.top_p,
                "stream": True,
            }
            if task.stop:
                payload["stop"] = task.stop

        logger.info(f"Sending request to vLLM: {endpoint}")
        yield StreamEvent.logs(
            log=f"Starting inference with {task.model_id}...",
            level="info"
        ).to_sse_format()

        # Stream from vLLM
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status_code != 200:
                    error_text = await response.atext()
                    logger.error(f"vLLM error: {error_text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"vLLM error: {error_text}"
                    )

                # Parse SSE stream from vLLM
                full_text = ""
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue

                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix

                        # Check for stream end
                        if data.strip() == "[DONE]":
                            break

                        try:
                            import json
                            chunk = json.loads(data)

                            # Extract delta from OpenAI format
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                choice = chunk["choices"][0]

                                # Handle chat completions format
                                if "delta" in choice:
                                    delta_content = choice["delta"].get("content", "")
                                    if delta_content:
                                        full_text += delta_content
                                        yield StreamEvent.text_delta(
                                            delta=delta_content
                                        ).to_sse_format()

                                # Handle completions format
                                elif "text" in choice:
                                    delta_content = choice["text"]
                                    if delta_content:
                                        full_text += delta_content
                                        yield StreamEvent.text_delta(
                                            delta=delta_content
                                        ).to_sse_format()

                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse vLLM chunk: {e}")
                            continue

        # Task completed successfully
        yield StreamEvent.logs(
            log=f"Generated {len(full_text)} characters",
            level="info"
        ).to_sse_format()

        yield StreamEvent.completed(
            status="completed",
            model=task.model_id
        ).to_sse_format()

        logger.info(f"Task {task.task_id} completed successfully")

    except Exception as e:
        logger.error(f"Error processing task {task.task_id}: {e}", exc_info=True)
        yield StreamEvent.logs(
            log=f"Error: {str(e)}",
            level="error"
        ).to_sse_format()
        yield StreamEvent.completed(
            status="failed",
            error=str(e)
        ).to_sse_format()


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health", response_model=WorkerHealthResponse)
async def health():
    """
    Health check endpoint.

    Returns healthy only if both worker and vLLM are operational.
    """
    vllm_healthy = await check_vllm_health()

    if vllm_healthy:
        return WorkerHealthResponse(status="healthy")
    else:
        return WorkerHealthResponse(status="unhealthy")


@app.post("/stop", response_model=WorkerStopResponse)
async def stop():
    """
    Stop worker gracefully (returns immediately, cleanup in background).

    Note: vLLM server will be stopped by container termination.
    """
    logger.info("Stop signal received")
    return WorkerStopResponse(status="stopping")


@app.post("/task")
async def submit_task(task: VLLMTaskRequest):
    """
    Submit LLM inference task with SSE streaming.

    Args:
        task: vLLM task request

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
    logger.info(f"Starting vLLM Worker on port {SERVER_PORT}...")
    logger.info(f"Will connect to vLLM server at {VLLM_BASE_URL}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVER_PORT,
        log_level="info"
    )
