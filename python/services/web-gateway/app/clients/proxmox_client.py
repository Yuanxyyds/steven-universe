"""
Proxmox API client for server monitoring.
"""

import logging

import httpx

from shared_schemas.web_server import NodeInfo

logger = logging.getLogger(__name__)


async def get_node_stats(
    client: httpx.AsyncClient,
    api_url: str,
    api_token: str,
    node_name: str
) -> NodeInfo:
    """
    Fetch statistics for a single Proxmox node.

    Args:
        client: HTTP client
        api_url: Proxmox API URL
        api_token: Proxmox API token
        node_name: Name of the node to query

    Returns:
        NodeInfo object with stats or offline status
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_token
    }

    try:
        # Fetch node status
        response = await client.get(
            f"{api_url}/nodes/{node_name}/status",
            headers=headers,
            timeout=5.0
        )

        if response.status_code == 200:
            data = response.json().get("data", {})

            # Extract memory stats
            memory_info = data.get("memory", {})
            memory_used = memory_info.get("used", 0)
            memory_total = memory_info.get("total", 1)
            memory_used_gb = memory_used / (1024 ** 3)
            memory_total_gb = memory_total / (1024 ** 3)
            memory_usage_percent = (
                memory_used / memory_total) * 100 if memory_total > 0 else 0

            # Extract CPU stats
            cpu_info = data.get("cpu", 0)
            cpuinfo = data.get("cpuinfo", {})
            cpu_cores = cpuinfo.get("cpus", None)
            cpu_usage_percent = cpu_info * 100

            logger.info(f"Successfully fetched stats for node: {node_name}")

            return NodeInfo(
                name=node_name,
                online=True,
                memory_used_gb=round(memory_used_gb, 2),
                memory_total_gb=round(memory_total_gb, 2),
                memory_usage_percent=round(memory_usage_percent, 2),
                cpu_usage_percent=round(cpu_usage_percent, 2),
                cpu_cores=cpu_cores,
                cpu_temp_celsius=None
            )
        else:
            logger.error(
                f"Failed to fetch stats for {node_name}: HTTP {response.status_code}")
            return NodeInfo(name=node_name, online=False)

    except httpx.RequestError as e:
        logger.error(f"Request error fetching stats for {node_name}: {e}")
        return NodeInfo(name=node_name, online=False)
    except Exception as e:
        logger.error(f"Unexpected error fetching stats for {node_name}: {e}")
        return NodeInfo(name=node_name, online=False)
