"""
Food classification endpoints.
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.dependencies import HTTPClient
from app.clients import food101_client
from shared_schemas.web_server import FoodClassificationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classifications", tags=["classifications"])


@router.post("/food", response_model=FoodClassificationResponse)
async def classify_food_image(
    client: HTTPClient,
    file: UploadFile = File(..., description="Food image to classify")
):
    """
    Classify uploaded food image.

    This endpoint will route to food101-service in Phase 3.
    Currently returns 501 Not Implemented.

    Args:
        file: Image file (JPG, PNG)

    Returns:
        Classification results from multiple models
    """
    logger.warning(f"Food classification requested for file: {file.filename}, but service not implemented")

    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png", "image/jpg"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG and PNG images are supported"
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Food101 service not yet implemented",
            "phase": "Phase 3",
            "filename": file.filename,
            "next_steps": "This will route to a separate food101-service microservice"
        }
    )
