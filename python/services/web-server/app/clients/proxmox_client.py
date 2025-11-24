"""
Proxmox API client for server monitoring.
"""

import logging
from typing import List

import httpx
import psutil

from app.core.config import settings
from shared_schemas.web_server import ServerNode

logger = logging.getLogger(__name__)


async def get_server_stats(client: httpx.AsyncClient) -> List[ServerNode]:
    """
    Fetch server statistics from Proxmox API.

    Returns:
        List of ServerNode objects with stats for each node
    """
    nodes = []
    node_names = ["local2"]

    headers = {
        "Content-Type": "application/json",
        "Authorization": settings.PROXMOX_API_TOKEN
    }

    for node_name in node_names:
        try:
            # Fetch node status
            response = await client.get(
                f"{settings.PROXMOX_API_URL}/nodes/{node_name}/status",
                headers=headers
            )

            if response.status_code == 200:
                data = response.json().get("data", {})

                # Extract memory stats
                memory_info = data.get("memory", {})
                memory_used = memory_info.get("used", 0)
                memory_total = memory_info.get("total", 1)
                memory_used_gb = memory_used / (1024 ** 3)  # Convert bytes to GB
                memory_total_gb = memory_total / (1024 ** 3)
                memory_usage_percent = (memory_used / memory_total) * 100 if memory_total > 0 else 0

                # Extract CPU stats
                cpu_info = data.get("cpu", 0)  # CPU usage as decimal (0.0 - 1.0)
                cpuinfo = data.get("cpuinfo", {})
                cpu_cores = cpuinfo.get("cpus", None)
                cpu_usage_percent = cpu_info * 100  # Convert to percentage

                # Get CPU temperature (only for local node using psutil)
                cpu_temp = None
                if node_name == "local":
                    try:
                        temps = psutil.sensors_temperatures()
                        if temps and "coretemp" in temps:
                            # Average temperature across all cores
                            core_temps = [entry.current for entry in temps["coretemp"]]
                            cpu_temp = sum(core_temps) / len(core_temps) if core_temps else None
                    except Exception as e:
                        logger.warning(f"Failed to get CPU temperature for {node_name}: {e}")

                nodes.append(ServerNode(
                    name=node_name,
                    status="online",
                    memory_used_gb=round(memory_used_gb, 2),
                    memory_total_gb=round(memory_total_gb, 2),
                    memory_usage_percent=round(memory_usage_percent, 2),
                    cpu_usage_percent=round(cpu_usage_percent, 2),
                    cpu_cores=cpu_cores,
                    cpu_temp_celsius=round(cpu_temp, 2) if cpu_temp else None
                ))

                logger.info(f"Successfully fetched stats for node: {node_name}")

            else:
                logger.error(f"Failed to fetch stats for {node_name}: HTTP {response.status_code}")
                nodes.append(ServerNode(
                    name=node_name,
                    status="offline"
                ))

        except httpx.RequestError as e:
            logger.error(f"Request error fetching stats for {node_name}: {e}")
            nodes.append(ServerNode(
                name=node_name,
                status="offline"
            ))
        except Exception as e:
            logger.error(f"Unexpected error fetching stats for {node_name}: {e}")
            nodes.append(ServerNode(
                name=node_name,
                status="offline"
            ))

    return nodes
