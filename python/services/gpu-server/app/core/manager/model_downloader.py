"""
Model downloader with automatic fetching from file-service.
"""

import os
import logging
import asyncio
import tarfile
import shutil
from pathlib import Path
from typing import Optional, Dict

import httpx

from app.core.config import settings
from app.clients.file_service_client import file_service_client

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
        """Scan cache directory for existing models (directories only, as tar.gz are extracted)."""
        try:
            for item in self._cache_dir.iterdir():
                if item.is_dir():
                    model_id = item.name
                    self._cache_registry[model_id] = str(item)
                    logger.debug(f"Found cached model directory: {model_id}")
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
        Fetch model tar.gz from file-service, extract, and save to cache.

        Downloads from: GET /internal/download/models/{model_id}.tar.gz
        Expected format: {model_id}.tar.gz
        Extracts to: {cache_dir}/{model_id}/

        Args:
            model_id: Model identifier (without .tar.gz extension)
            http_client: HTTP client for file-service requests

        Returns:
            Local path to extracted model directory, or None if failed
        """
        # Prevent concurrent fetches of same model
        if model_id not in self._fetch_locks:
            self._fetch_locks[model_id] = asyncio.Lock()

        async with self._fetch_locks[model_id]:
            # Check again in case another task fetched it
            if model_id in self._cache_registry:
                return self._cache_registry[model_id]

            logger.info(f"Fetching model {model_id} from file-service...")

            tar_path = self._cache_dir / f"{model_id}.tar.gz"
            model_dir = self._cache_dir / model_id

            try:
                # Download tar.gz from file-service
                success = await file_service_client.download_model(
                    model_id=model_id,
                    destination_path=tar_path,
                    http_client=http_client
                )

                if not success:
                    logger.error(f"Failed to download model {model_id}")
                    return None

                logger.info(f"Extracting model {model_id} to {model_dir}...")

                # Create model directory
                model_dir.mkdir(parents=True, exist_ok=True)

                # Extract tar.gz with path traversal validation
                with tarfile.open(tar_path, 'r:gz') as tar:
                    # Validate all paths to prevent traversal attacks
                    for member in tar.getmembers():
                        member_path = model_dir / member.name
                        try:
                            resolved = member_path.resolve()
                            if not str(resolved).startswith(str(model_dir.resolve())):
                                raise ValueError(f"Path traversal attempt detected: {member.name}")
                        except Exception as e:
                            logger.error(f"Invalid path in tar: {member.name} - {e}")
                            raise ValueError(f"Invalid archive member: {member.name}")

                    # Extract all files
                    tar.extractall(path=model_dir)

                logger.info(f"Extraction complete to {model_dir}")

                # Cleanup tar.gz after successful extraction
                if tar_path.exists():
                    tar_path.unlink()
                    logger.debug(f"Cleaned up tar.gz: {tar_path}")

                # Register extracted directory in cache
                model_dir_str = str(model_dir)
                self._cache_registry[model_id] = model_dir_str

                logger.info(f"Successfully cached model {model_id} at {model_dir_str}")
                return model_dir_str

            except tarfile.TarError as e:
                logger.error(f"Failed to extract tar.gz for model {model_id}: {e}")
                self._cleanup_failed_download(tar_path, model_dir)
                return None
            except Exception as e:
                logger.error(f"Error fetching/extracting model {model_id}: {e}", exc_info=True)
                self._cleanup_failed_download(tar_path, model_dir)
                return None

    def _cleanup_failed_download(self, tar_path: Path, model_dir: Path):
        """Cleanup partial downloads on failure."""
        try:
            if tar_path.exists():
                tar_path.unlink()
                logger.debug(f"Cleaned up partial tar.gz: {tar_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup tar.gz: {e}")

        try:
            if model_dir.exists():
                shutil.rmtree(model_dir)
                logger.debug(f"Cleaned up partial extraction: {model_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup model directory: {e}")

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
