"""
Food101 service client.
Routes food classification requests to the food101-service microservice.
"""

import logging

import httpx
from fastapi import UploadFile

from app.core.config import settings
from shared_schemas.web_server import FoodClassificationResponse

logger = logging.getLogger(__name__)


async def classify_food_image(
    client: httpx.AsyncClient,
    file: UploadFile
) -> FoodClassificationResponse:
    """
    Send food image to food101-service for classification.

    Args:
        client: HTTP client
        file: Uploaded image file

    Returns:
        Classification results from food101-service

    Raises:
        httpx.HTTPStatusError: If service returns error
    """
    # TODO: Implement when food101-service is ready
    # For now, return stub response
    logger.warning("food101-service not yet implemented, returning stub")

    raise NotImplementedError(
        "Food101 service not yet implemented. "
        "This will route to a separate microservice in Phase 3."
    )
