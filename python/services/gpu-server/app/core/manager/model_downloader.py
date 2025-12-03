"""
Model downloader with automatic fetching from file-service.
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelDownloader:
    """
    Downloads and manages models with automatic fetching from file-service.

    Implements hybrid approach:
    1. Check if model exists on host
    2. If not found, fetch from file-service
    3. Save to host for future use
    4. Return host path for volume mount
    """

    def __init__(self):
        self._cache_dir = Path(settings.MODEL_CACHE_DIR)
        self._cache_registry: Dict[str, str] = {}  # model_id -> host_path
        self._fetch_locks: Dict[str, asyncio.Lock] = {}  # Prevent concurrent fetches
        self._initialized = False

    async def initialize(self):
        """Initialize model cache directory."""
        if self._initialized:
            return

        logger.info(f"Initializing Model Downloader at {self._cache_dir}")

        # Create cache directory if it doesn't exist
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Model cache directory ready: {self._cache_dir}")
        except Exception as e:
            logger.error(f"Failed to create cache directory: {e}")
            raise

        # Scan existing cached models
        await self._scan_existing_models()

        self._initialized = True
        logger.info(f"Model Downloader initialized with {len(self._cache_registry)} cached models")

    async def _scan_existing_models(self):
        """Scan cache directory for existing models."""
        try:
            for item in self._cache_dir.iterdir():
                if item.is_dir() or item.is_file():
                    model_id = item.name
                    self._cache_registry[model_id] = str(item)
                    logger.debug(f"Found cached model: {model_id}")
        except Exception as e:
            logger.error(f"Error scanning existing models: {e}")

    async def get_model_path(
        self,
        model_id: str,
        http_client: httpx.AsyncClient
    ) -> Optional[str]:
        """
        Get local path for model, fetching from file-service if needed.

        Args:
            model_id: Model identifier
            http_client: HTTP client for file-service requests

        Returns:
            Local host path to model, or None if fetch failed
        """
        # Check if already cached
        if model_id in self._cache_registry:
            path = self._cache_registry[model_id]
            if os.path.exists(path):
                logger.info(f"Model {model_id} found in cache: {path}")
                return path
            else:
                logger.warning(f"Cached model {model_id} no longer exists at {path}, will re-fetch")
                del self._cache_registry[model_id]

        # Auto-fetch if enabled
        if not settings.AUTO_FETCH_MODELS:
            logger.warning(f"Model {model_id} not in cache and auto-fetch disabled")
            return None

        # Fetch from file-service
        return await self._fetch_model(model_id, http_client)

    async def _fetch_model(
        self,
        model_id: str,
        http_client: httpx.AsyncClient
    ) -> Optional[str]:
        """
        Fetch model from file-service and save to cache.

        Args:
            model_id: Model identifier
            http_client: HTTP client for file-service requests

        Returns:
            Local path to downloaded model, or None if failed
        """
        # Prevent concurrent fetches of same model
        if model_id not in self._fetch_locks:
            self._fetch_locks[model_id] = asyncio.Lock()

        async with self._fetch_locks[model_id]:
            # Check again in case another task fetched it
            if model_id in self._cache_registry:
                return self._cache_registry[model_id]

            logger.info(f"Fetching model {model_id} from file-service...")

            try:
                # Request model from file-service
                # Assuming file-service has an internal API for model access
                response = await http_client.get(
                    f"{settings.FILE_SERVICE_URL}/internal/models/{model_id}",
                    headers={"X-Internal-Key": settings.FILE_SERVICE_INTERNAL_KEY},
                    timeout=300.0  # 5 minute timeout for large models
                )

                if response.status_code != 200:
                    logger.error(f"Failed to fetch model {model_id}: HTTP {response.status_code}")
                    return None

                # Save model to cache
                model_path = self._cache_dir / model_id
                model_path.parent.mkdir(parents=True, exist_ok=True)

                # Write model data
                with open(model_path, 'wb') as f:
                    f.write(response.content)

                # Register in cache
                model_path_str = str(model_path)
                self._cache_registry[model_id] = model_path_str

                logger.info(f"Successfully cached model {model_id} at {model_path_str}")
                return model_path_str

            except httpx.TimeoutException:
                logger.error(f"Timeout fetching model {model_id} from file-service")
                return None
            except Exception as e:
                logger.error(f"Error fetching model {model_id}: {e}")
                return None

    def get_cached_models(self) -> Dict[str, str]:
        """Get dictionary of all cached models."""
        return self._cache_registry.copy()

    async def clear_cache(self, model_id: Optional[str] = None):
        """
        Clear model cache.

        Args:
            model_id: Specific model to clear, or None to clear all
        """
        if model_id:
            if model_id in self._cache_registry:
                path = self._cache_registry[model_id]
                try:
                    if os.path.exists(path):
                        os.remove(path)
                    del self._cache_registry[model_id]
                    logger.info(f"Cleared cached model: {model_id}")
                except Exception as e:
                    logger.error(f"Error clearing model {model_id}: {e}")
        else:
            # Clear all cached models
            for model_id, path in list(self._cache_registry.items()):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    logger.error(f"Error removing {path}: {e}")

            self._cache_registry.clear()
            logger.info("Cleared all cached models")


# Global model downloader instance (singleton)
model_downloader = ModelDownloader()
