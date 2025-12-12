"""
Docker Manager - Manages Docker containers using DOOD pattern.

Handles:
- Creating session containers (long-lived)
- GPU passthrough via --gpus device=N
- Volume mounts for models
- Container lifecycle management
- Health monitoring
"""

import asyncio
import logging
from typing import Dict, List, Optional, AsyncIterator
import docker
from docker.types import DeviceRequest

from app.core.config import settings

logger = logging.getLogger(__name__)


class DockerManager:
    """
    Manages Docker containers via Docker-outside-of-Docker (DOOD) pattern.

    The service itself runs in a container with Docker socket mounted,
    allowing it to create sibling containers with GPU access.
    """

    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._initialized = False

    async def initialize(self):
        """Initialize Docker client."""
        if self._initialized:
            return

        logger.info("Initializing Docker Manager...")

        try:
            # Use from_env() which auto-detects the Docker socket
            # This is more reliable than manually specifying the socket path
            self._client = docker.from_env()

            # Test connection
            self._client.ping()
            logger.info("Docker client initialized and connected")

            # Log Docker info
            info = self._client.info()
            logger.info(f"Docker version: {info.get('ServerVersion', 'unknown')}")

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise

    async def shutdown(self):
        """Shutdown Docker manager."""
        logger.info("Shutting down Docker Manager...")

        if self._client:
            self._client.close()

        self._initialized = False
        logger.info("Docker Manager shutdown complete")

    async def create_session_container(
        self,
        session_id: str,
        gpu_id: int,
        model_id: str,
        docker_image: str,
        command: List[str],
        env_vars: Dict[str, str],
        model_host_path: str,
        worker_client_path: str
    ) -> str:
        """
        Create a long-lived session container.

        Args:
            session_id: Session identifier
            gpu_id: GPU device ID to allocate
            model_id: Model identifier
            docker_image: Docker image to use
            command: Command to execute
            env_vars: Environment variables
            model_host_path: Host path to model directory
            worker_client_path: Import path to worker client (for health checks)

        Returns:
            Container ID

        Raises:
            docker.errors.DockerException: If container creation fails
        """
        logger.info(f"Creating session container for session {session_id} on GPU {gpu_id}")

        try:
            # Prepare environment variables
            env = {
                **env_vars,
                "MODEL_PATH": "/models",  # Container path where model is mounted
                "SESSION_ID": session_id,
            }

            # Prepare volume mounts
            volumes = {
                model_host_path: {
                    "bind": "/models",
                    "mode": "ro"  # Read-only
                }
            }

            # GPU device request
            device_requests = [
                DeviceRequest(
                    device_ids=[str(gpu_id)],
                    capabilities=[["gpu"]]
                )
            ]

            # Create container (blocking operation - run in thread pool)
            def _create_container_sync():
                """Synchronous container creation - runs in thread pool."""
                container = self._client.containers.run(
                    image=docker_image,
                    command=command,
                    environment=env,
                    volumes=volumes,
                    device_requests=device_requests,
                    network="gpu-network",  # Custom network for container DNS resolution
                    detach=True,
                    remove=False,  # Do NOT auto-remove (session is long-lived)
                    stdin_open=True,  # Keep stdin open for commands
                    tty=False,
                    mem_limit=settings.TASK_MEMORY_LIMIT,
                    cpu_quota=settings.TASK_CPU_QUOTA,
                    labels={
                        "gpu-service.session_id": session_id,
                        "gpu-service.model_id": model_id,
                        "gpu-service.gpu_id": str(gpu_id)
                    }
                )
                # Set container name after creation using container ID
                container.rename(f"gpu-session-{container.id[:12]}")
                return container

            container = await asyncio.to_thread(_create_container_sync)

            logger.info(f"Created session container {container.id[:12]} for session {session_id}")

            # Start background health monitoring for this container (docker manager responsibility)
            asyncio.create_task(
                self._monitor_container_health(container.id, session_id, worker_client_path)
            )

            return container.id

        except docker.errors.ImageNotFound:
            logger.error(f"Docker image not found: {docker_image}")
            raise
        except docker.errors.APIError as e:
            logger.error(f"Docker API error creating session container: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating session container: {e}", exc_info=True)
            raise

    async def _monitor_container_health(
        self,
        container_id: str,
        session_id: str,
        worker_client_path: str,
        startup_timeout: int = 30
    ):
        """
        Monitor container health during startup.

        Polls /health endpoint until ready, then updates session status.
        Session lifecycle monitoring (idle/lifetime) is handled by SessionManager.

        Args:
            container_id: Container to monitor
            session_id: Session ID to update
            worker_client_path: Import path to worker client (for dynamic loading)
            startup_timeout: Max seconds to wait for initial health check
        """
        from app.core.manager.session_manager import session_manager
        from app.clients.worker.registry import worker_client_registry
        from shared_schemas.gpu_service import WorkerStatus

        container_name = f"gpu-session-{container_id[:12]}"
        logger.info(f"Starting health monitoring for {container_name}")

        # Get worker client dynamically
        worker_client = worker_client_registry.get_client(worker_client_path)

        # Wait for container to become healthy using worker-specific client
        is_healthy = await worker_client.wait_until_healthy(
            container_id=container_id,
            timeout=startup_timeout,
            retry_interval=1.0
        )

        if is_healthy:
            # Worker is ready, update session status and get updated session
            session = await session_manager.update_session_status(session_id, WorkerStatus.WAITING)

            # Signal ready event if handler is waiting
            if session:
                session.signal_ready()

            logger.info(f"Container {container_name} is healthy, session status updated to WAITING")
        else:
            # Health check failed
            logger.error(f"Container {container_name} failed health check")
            session = await session_manager.update_session_status(session_id, WorkerStatus.KILLED)

            # Signal ready event with failure (so handler doesn't hang)
            if session:
                session.signal_ready()


    async def execute_command_in_container(
        self,
        container_id: str,
        command: str
    ) -> Optional[str]:
        """
        Execute command in running container via docker exec.

        Args:
            container_id: Container ID
            command: Command to execute

        Returns:
            Command output, or None if failed
        """
        try:
            container = self._client.containers.get(container_id)

            # Execute command
            result = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                stdin=False,
                tty=False
            )

            output = result.output.decode('utf-8') if result.output else ""
            logger.debug(f"Executed command in {container_id[:12]}: {command} (exit_code={result.exit_code})")

            return output

        except docker.errors.NotFound:
            logger.error(f"Container {container_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error executing command in container {container_id}: {e}")
            return None

    async def stream_logs(
        self,
        container_id: str,
        follow: bool = True
    ) -> AsyncIterator[str]:
        """
        Stream logs from container.

        Args:
            container_id: Container ID
            follow: If True, follow log output (like docker logs --follow)

        Yields:
            Log lines as strings
        """
        try:
            container = self._client.containers.get(container_id)

            # Stream logs
            log_generator = container.logs(
                stdout=True,
                stderr=True,
                stream=True,
                follow=follow,
                timestamps=False
            )

            # Use asyncio.to_thread to prevent blocking the event loop
            # The docker-py log_generator blocks on I/O, so we need to run it in a thread
            loop = asyncio.get_event_loop()

            def read_next_log():
                """Blocking call to get next log line - runs in thread pool."""
                try:
                    return next(log_generator)
                except StopIteration:
                    return None

            while True:
                # Run blocking operation in thread pool
                log_bytes = await loop.run_in_executor(None, read_next_log)

                if log_bytes is None:
                    break

                line = log_bytes.decode('utf-8').rstrip()
                yield line

        except docker.errors.NotFound:
            logger.error(f"Container {container_id} not found for log streaming")
        except Exception as e:
            logger.error(f"Error streaming logs from {container_id}: {e}")

    async def stop_container(self, container_id: str, timeout: int = 10):
        """
        Stop container gracefully.

        Args:
            container_id: Container ID
            timeout: Timeout in seconds before force kill
        """
        def _stop_sync():
            """Synchronous stop operation - runs in thread pool."""
            try:
                container = self._client.containers.get(container_id)
                container.stop(timeout=timeout)
                logger.info(f"Stopped container {container_id[:12]}")
            except docker.errors.NotFound:
                logger.warning(f"Container {container_id} not found (already removed?)")
            except Exception as e:
                logger.error(f"Error stopping container {container_id}: {e}")
                raise

        # Run blocking Docker operation in thread pool
        try:
            await asyncio.to_thread(_stop_sync)
        except Exception:
            # Exception already logged in _stop_sync
            pass

    async def remove_container(self, container_id: str, force: bool = False):
        """
        Remove container.

        Args:
            container_id: Container ID
            force: Force removal even if running
        """
        try:
            container = self._client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Removed container {container_id[:12]}")

        except docker.errors.NotFound:
            logger.warning(f"Container {container_id} not found (already removed?)")
        except Exception as e:
            logger.error(f"Error removing container {container_id}: {e}")

    async def get_container_status(self, container_id: str) -> Optional[Dict]:
        """
        Get container status.

        Args:
            container_id: Container ID

        Returns:
            Container status dict, or None if not found
        """
        try:
            container = self._client.containers.get(container_id)
            container.reload()  # Refresh status

            return {
                "id": container.id,
                "status": container.status,
                "name": container.name,
                "created": container.attrs.get("Created"),
                "started_at": container.attrs.get("State", {}).get("StartedAt"),
                "finished_at": container.attrs.get("State", {}).get("FinishedAt"),
                "exit_code": container.attrs.get("State", {}).get("ExitCode")
            }

        except docker.errors.NotFound:
            logger.warning(f"Container {container_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting container status {container_id}: {e}")
            return None


# Global docker manager instance
docker_manager = DockerManager()
