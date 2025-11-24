"""
Health check endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.dependencies import HTTPClient
from shared_schemas.web_server import HealthResponse, ServiceStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health_status():
    """
    Basic health check endpoint.

    Returns service status and version.
    """
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION
    )


@router.get("/health/services", response_model=HealthResponse)
async def get_services_status(client: HTTPClient):
    """
    Check health of all downstream services.

    Returns status of each configured microservice.
    """
    services = []

    # Check Proxmox API
    try:
        response = await client.get(
            f"{settings.PROXMOX_API_URL}/version",
            headers={"Authorization": settings.PROXMOX_API_TOKEN},
            timeout=5.0
        )
        services.append(ServiceStatus(
            name="Proxmox API",
            url=settings.PROXMOX_API_URL,
            status="online" if response.status_code == 200 else "offline",
            response_time_ms=response.elapsed.total_seconds() * 1000
        ))
    except Exception as e:
        logger.error(f"Proxmox health check failed: {e}")
        services.append(ServiceStatus(
            name="Proxmox API",
            url=settings.PROXMOX_API_URL,
            status="offline"
        ))

    # Check File Service
    try:
        response = await client.get(
            f"{settings.FILE_SERVICE_URL}/health",
            timeout=5.0
        )
        services.append(ServiceStatus(
            name="File Service",
            url=settings.FILE_SERVICE_URL,
            status="online" if response.status_code == 200 else "offline",
            response_time_ms=response.elapsed.total_seconds() * 1000
        ))
    except Exception as e:
        logger.error(f"File service health check failed: {e}")
        services.append(ServiceStatus(
            name="File Service",
            url=settings.FILE_SERVICE_URL,
            status="offline"
        ))

    # Check future services (will be offline for now)
    future_services = [
        ("StevenAI Service", settings.STEVENAI_SERVICE_URL),
        ("Food101 Service", settings.FOOD101_SERVICE_URL),
        ("Landsink Service", settings.LANDSINK_SERVICE_URL),
    ]

    for name, url in future_services:
        try:
            response = await client.get(f"{url}/health", timeout=2.0)
            services.append(ServiceStatus(
                name=name,
                url=url,
                status="online" if response.status_code == 200 else "offline",
                response_time_ms=response.elapsed.total_seconds() * 1000
            ))
        except Exception:
            services.append(ServiceStatus(
                name=name,
                url=url,
                status="offline"
            ))

    # Determine overall health
    online_count = sum(1 for s in services if s.status == "online")
    total_count = len(services)

    if online_count == total_count:
        overall_status = "healthy"
    elif online_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        services=services
    )
