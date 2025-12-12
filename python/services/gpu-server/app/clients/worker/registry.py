"""
Worker Client Registry - Manages singleton instances of worker clients.

Provides:
- Dynamic client loading by import path
- Singleton management (one instance per worker type)
- Type validation (ensures clients inherit from GPUWorkerProtocol)
"""

import logging
import importlib
from typing import Dict, Type

from app.clients.worker.base import GPUWorkerProtocol

logger = logging.getLogger(__name__)


class WorkerClientRegistry:
    """
    Registry for worker client singletons.

    Dynamically loads worker clients by import path and caches instances.
    """

    def __init__(self):
        self._clients: Dict[str, GPUWorkerProtocol] = {}
        self._client_classes: Dict[str, Type[GPUWorkerProtocol]] = {}

    def _load_client_class(self, import_path: str) -> Type[GPUWorkerProtocol]:
        """
        Dynamically import and validate client class.

        Args:
            import_path: Full import path (e.g., "app.clients.worker.test.download_pipeline.DownloadPipelineClient")

        Returns:
            Client class

        Raises:
            ImportError: If module/class not found
            TypeError: If class doesn't inherit from GPUWorkerProtocol
            ValueError: If import path is from untrusted namespace
        """
        # Validate import path starts with allowed prefix (security)
        if not import_path.startswith("app.clients.worker."):
            raise ValueError(
                f"Invalid worker client path: {import_path}. "
                f"Must start with 'app.clients.worker.'"
            )

        # Parse import path
        module_path, class_name = import_path.rsplit('.', 1)

        # Import module
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            logger.error(f"Failed to import module {module_path}: {e}")
            raise ImportError(f"Worker client module not found: {module_path}")

        # Get class
        try:
            client_class = getattr(module, class_name)
        except AttributeError:
            logger.error(f"Class {class_name} not found in module {module_path}")
            raise ImportError(f"Worker client class not found: {class_name}")

        # Validate class inherits from GPUWorkerProtocol
        if not issubclass(client_class, GPUWorkerProtocol):
            raise TypeError(
                f"Worker client {import_path} must inherit from GPUWorkerProtocol"
            )

        logger.info(f"Loaded worker client class: {import_path}")
        return client_class

    def get_client(self, import_path: str) -> GPUWorkerProtocol:
        """
        Get or create singleton client instance.

        Args:
            import_path: Full import path to client class

        Returns:
            Singleton client instance
        """
        # Return cached instance if exists
        if import_path in self._clients:
            return self._clients[import_path]

        # Load class if not cached
        if import_path not in self._client_classes:
            self._client_classes[import_path] = self._load_client_class(import_path)

        # Create singleton instance
        client_class = self._client_classes[import_path]
        client_instance = client_class()
        self._clients[import_path] = client_instance

        logger.info(f"Created singleton worker client: {import_path}")
        return client_instance

    def clear(self):
        """Clear all cached clients (for testing)."""
        self._clients.clear()
        self._client_classes.clear()


# Global singleton registry
worker_client_registry = WorkerClientRegistry()
