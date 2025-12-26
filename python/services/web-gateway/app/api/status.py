"""
Unified status endpoint combining health checks and server stats.
"""

import logging
import time
from typing import Dict

from fastapi import APIRouter, HTTPException, status as http_status

from app.core.config import settings
from app.core.dependencies import HTTPClient
from app.clients import proxmox_client
from shared_schemas.web_server import (
    UnifiedStatusResponse,
    ServerInfo,
    NodeInfo,
    ServiceInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["status"])


async def check_service_health(
    client: HTTPClient, service_name: str
) -> ServiceInfo:
    """Check health of a single service."""
    service_url, api_key = settings.get_service_config(service_name)

    if not service_url:
        logger.warning(f"No URL configured for service: {service_name}")
        return ServiceInfo(name=service_name, online=False)

    try:
        start_time = time.time()
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key

        response = await client.get(
            f"{service_url}/health", headers=headers, timeout=5.0
        )
        response_time_ms = (time.time() - start_time) * 1000

        return ServiceInfo(
            name=service_name,
            online=response.status_code == 200,
            response_time_ms=round(response_time_ms, 2),
        )
    except Exception as e:
        logger.error(f"Service health check failed for {service_name}: {e}")
        return ServiceInfo(name=service_name, online=False)


async def get_node_info(
    client: HTTPClient, server_name: str, node_name: str, services: Dict[str, dict]
) -> NodeInfo:
    """Get information about a Proxmox node including stats and service health."""
    api_url, api_token = settings.get_server_config(server_name)

    if not api_url or not api_token:
        logger.warning(
            f"No API config for server {server_name}, skipping node {node_name}"
        )
        return NodeInfo(name=node_name, online=False)

    # Get node stats from Proxmox client
    node_info = await proxmox_client.get_node_stats(
        client, api_url, api_token, node_name
    )

    # Check services running on this node
    for service_name, service_config in services.items():
        # Extract the node name from the service config
        service_node = service_config.get("node")
        if service_node == node_name:
            service_info = await check_service_health(client, service_name)
            node_info.services[service_name] = service_info

    return node_info


@router.get("/status", response_model=UnifiedStatusResponse)
async def get_unified_status(client: HTTPClient):
    """
    Get unified status combining server stats and service health.

    Returns hierarchical structure:
    - servers (dict of server_name -> ServerInfo)
      - nodes (dict of node_name -> NodeInfo)
        - services (dict of service_name -> ServiceInfo)
    """
    try:
        # Load status configuration from YAML
        config = settings.load_status_config()
        servers_config = config.get("servers", {})

        servers: Dict[str, ServerInfo] = {}

        # Iterate through each server
        for server_name, server_config in servers_config.items():
            nodes_list = server_config.get("nodes", [])
            services_config = server_config.get("services", {})

            server_info = ServerInfo(name=server_name, online=False)
            nodes: Dict[str, NodeInfo] = {}

            # Get info for each node in this server
            for node_name in nodes_list:
                node_info = await get_node_info(
                    client, server_name, node_name, services_config
                )
                nodes[node_name] = node_info

                # Server is online if at least one node is online
                if node_info.online:
                    server_info.online = True

            server_info.nodes = nodes
            servers[server_name] = server_info

        # Determine overall status
        total_nodes = sum(len(s.nodes) for s in servers.values())
        online_nodes = sum(
            1 for s in servers.values() for n in s.nodes.values() if n.online
        )
        total_services = sum(
            len(n.services)
            for s in servers.values()
            for n in s.nodes.values()
        )
        online_services = sum(
            1
            for s in servers.values()
            for n in s.nodes.values()
            for svc in n.services.values()
            if svc.online
        )

        # Calculate overall health
        if total_nodes == 0:
            overall_status = "unhealthy"
        elif online_nodes == total_nodes and (
            total_services == 0 or online_services == total_services
        ):
            overall_status = "healthy"
        elif online_nodes > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        return UnifiedStatusResponse(status=overall_status, servers=servers)

    except FileNotFoundError as e:
        logger.error(f"Status config file not found: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Status configuration file not found",
        )
    except Exception as e:
        logger.error(f"Failed to get unified status: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch unified status",
        )
