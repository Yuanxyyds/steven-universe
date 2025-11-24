"""
Climate prediction endpoints (Land Sink).
"""

import logging

from fastapi import APIRouter, HTTPException, Query, status

from shared_schemas.web_server import LandsinkPredictionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/landsink", response_model=LandsinkPredictionResponse)
async def predict_landsink(
    year: int = Query(default=2023, ge=1900, le=2200, description="Year to predict")
):
    """
    Predict land sink percentage for a given year.

    This endpoint will route to landsink-service in Phase 4.
    Currently returns 501 Not Implemented.

    Args:
        year: Year to predict (1900-2200)

    Returns:
        Prediction with temperature, sea level, and interactive map
    """
    logger.warning(f"Landsink prediction requested for year {year}, but service not implemented")

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Landsink service not yet implemented",
            "phase": "Phase 4",
            "requested_year": year,
            "next_steps": "This will route to a separate landsink-service microservice"
        }
    )
