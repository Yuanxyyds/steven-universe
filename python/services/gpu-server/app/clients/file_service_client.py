"""
File Service Client - Interface to file-service for model downloads.
"""

import logging
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class FileServiceClient:
    """
    Client for communicating with file-service.

    Handles model downloads with streaming support for large files.
    """

    def __init__(self):
        self.base_url = settings.FILE_SERVICE_URL
        self.internal_key = settings.FILE_SERVICE_INTERNAL_KEY
        self.timeout = 300.0  # 5 minute timeout for large models

    async def download_model(
        self,
        model_id: str,
        destination_path: Path,
        http_client: httpx.AsyncClient
    ) -> bool:
        """
        Download model tar.gz from file-service.

        Downloads from: GET /internal/download/{bucket}/{key:path}
        For models: bucket="models", key="{model_id}.tar.gz"
        Expected response: tar.gz file as binary stream

        Args:
            model_id: Model identifier (without .tar.gz extension)
            destination_path: Path where to save the tar.gz file
            http_client: HTTP client for requests

        Returns:
            True if download successful, False otherwise
        """
        try:
            # File service endpoint: GET /internal/download/{bucket}/{key:path}
            url = f"{self.base_url}/internal/download/models/{model_id}.tar.gz"
            headers = {"Authorization": f"Bearer {self.internal_key}"}

            logger.info(f"Downloading model {model_id}.tar.gz from file-service: {url}")

            # Stream download for large files
            async with http_client.stream('GET', url, headers=headers, timeout=self.timeout) as response:
                if response.status_code != 200:
                    logger.error(
                        f"Failed to download model {model_id}: "
                        f"HTTP {response.status_code} - {response.text}"
                    )
                    return False

                # Write to file in chunks
                destination_path.parent.mkdir(parents=True, exist_ok=True)

                with open(destination_path, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

            logger.info(f"Successfully downloaded model {model_id} to {destination_path}")
            return True

        except httpx.TimeoutException:
            logger.error(f"Timeout downloading model {model_id} from file-service")
            return False
        except Exception as e:
            logger.error(f"Error downloading model {model_id}: {e}", exc_info=True)
            return False


# Global file service client instance (singleton)
file_service_client = FileServiceClient()
