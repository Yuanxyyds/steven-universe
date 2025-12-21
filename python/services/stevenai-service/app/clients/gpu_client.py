"""
GPU Service Client - Communicates with gpu-service for inference.
"""

import json
import logging
from typing import AsyncIterator, List, Dict, Any

import httpx
from httpx_sse import aconnect_sse

from app.core.config import settings
from shared_schemas.sse import StreamEvent, EventType

logger = logging.getLogger(__name__)


class GPUClient:
    """Client for gpu-service predefined tasks."""

    async def check_health(self) -> bool:
        """
        Check if GPU service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(
                timeout=settings.GPU_SERVICE_HEALTH_CHECK_TIMEOUT
            ) as client:
                response = await client.get(
                    f"{settings.GPU_SERVICE_URL}/health"
                )
                if response.status_code == 200:
                    logger.info("GPU service health check: OK")
                    return True
                else:
                    logger.warning(f"GPU service health check failed: HTTP {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"GPU service health check failed: {e}")
            return False

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 512
    ) -> AsyncIterator[str]:
        """
        Stream chat completion from GPU service.

        Uses the predefined task "vllm-chat".

        Args:
            messages: OpenAI-style messages
            model_id: Model identifier for gpu-service
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Yields:
            Text deltas
        """
        task_request = {
            "task_name": "vllm-chat",
            "model_id": model_id,
            "metadata": {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        }

        url = f"{settings.GPU_SERVICE_URL}/api/tasks/predefined"
        headers = {
            "X-API-Key": settings.GPU_SERVICE_API_KEY,
            "Accept": "text/event-stream"
        }

        logger.info(f"Streaming chat from GPU service: model={model_id}")

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with aconnect_sse(
                    client,
                    "POST",
                    url,
                    json=task_request,
                    headers=headers
                ) as event_source:
                    async for sse_event in event_source.aiter_sse():
                        try:
                            # Skip empty events (keep-alive, comments)
                            if not sse_event.data or not sse_event.data.strip():
                                continue

                            # Parse JSON data and deserialize to StreamEvent
                            data_dict = json.loads(sse_event.data)
                            event = StreamEvent.from_dict(data_dict)

                            if event.event_type == EventType.TEXT_DELTA:
                                delta = event.data.get("delta", "")
                                if delta:
                                    yield delta

                            elif event.event_type == EventType.COMPLETED:
                                # Check completion status
                                status = event.data.get("status", "unknown")

                                if status == "completed":
                                    logger.info("GPU service streaming completed successfully")
                                    break
                                else:
                                    # Failed, timeout, or other non-success status
                                    error = event.data.get("error", f"Task failed with status: {status}")
                                    logger.error(f"GPU service task failed: {error}")
                                    raise RuntimeError(f"GPU service task failed: {error}")

                        except (json.JSONDecodeError, ValueError) as e:
                            logger.warning(f"Failed to parse SSE event: {e}")
                        except Exception as e:
                            logger.error(f"Error processing SSE event: {e}")
                            raise

        except Exception as e:
            logger.error(f"GPU service streaming error: {e}", exc_info=True)
            raise


# Global instance
gpu_client = GPUClient()
