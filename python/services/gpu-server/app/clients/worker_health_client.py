"""
Worker Health Check Client - Monitors worker container health.

Handles:
- Health endpoint polling for session workers
- HTTP communication over Docker internal network
- Retry logic with configurable timeouts
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class WorkerHealthClient:
    """
    Client for checking worker container health.

    Uses Docker internal networking (container name DNS resolution)
    to communicate with worker containers.
    """

    def __init__(self, timeout: float = 2.0):
        """
        Initialize health check client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    async def check_health(self, container_id: str) -> bool:
        """
        Check if a worker container is healthy.

        Args:
            container_id: Container ID to check

        Returns:
            True if healthy (200 response), False otherwise
        """
        container_name = f"gpu-session-{container_id[:12]}"
        health_url = f"http://{container_name}:8000/health"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url, timeout=self.timeout)

                if response.status_code == 200:
                    logger.debug(f"Container {container_name} is healthy")
                    return True
                else:
                    logger.debug(
                        f"Container {container_name} unhealthy: "
                        f"status={response.status_code}"
                    )
                    return False

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
            logger.debug(f"Container {container_name} health check failed: {e}")
            return False

        except Exception as e:
            logger.error(
                f"Unexpected error checking health for {container_name}: {e}",
                exc_info=True
            )
            return False

    async def wait_until_healthy(
        self,
        container_id: str,
        timeout: int = 30,
        retry_interval: float = 1.0
    ) -> bool:
        """
        Wait for a worker container to become healthy.

        Polls the health endpoint until it returns 200 or timeout is reached.

        Args:
            container_id: Container ID to check
            timeout: Max seconds to wait
            retry_interval: Seconds between retries

        Returns:
            True if became healthy within timeout, False otherwise
        """
        import asyncio

        container_name = f"gpu-session-{container_id[:12]}"
        logger.info(f"Waiting for {container_name} to become healthy (timeout: {timeout}s)")

        start_time = asyncio.get_event_loop().time()

        while True:
            # Check health
            is_healthy = await self.check_health(container_id)

            if is_healthy:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info(
                    f"Container {container_name} is healthy "
                    f"(elapsed: {elapsed:.1f}s)"
                )
                return True

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.error(
                    f"Container {container_name} health check timeout "
                    f"after {timeout}s"
                )
                return False

            # Wait before retry
            await asyncio.sleep(retry_interval)


# Singleton instance
worker_health_client = WorkerHealthClient()
