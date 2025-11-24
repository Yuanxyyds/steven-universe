"""
Server statistics endpoints (Proxmox monitoring).
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import HTTPClient
from app.clients import proxmox_client
from shared_schemas.web_server import ServerStatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/servers", response_model=ServerStatsResponse)
async def get_server_stats(client: HTTPClient):
    """
    Get server statistics from Proxmox.

    Returns CPU, memory, and temperature stats for all configured nodes.
    """
    try:
        nodes = await proxmox_client.get_server_stats(client)

        return ServerStatsResponse(
            success=True,
            nodes=nodes
        )

    except Exception as e:
        logger.error(f"Failed to get server stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch server statistics"
        )
