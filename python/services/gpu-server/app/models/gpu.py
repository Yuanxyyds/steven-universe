"""
GPU device data models.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GPUDevice:
    """Represents a single GPU device."""
    device_id: int
    name: str
    memory_total_mb: int
    memory_used_mb: int = 0
    temperature_celsius: float = 0.0
    utilization_percent: float = 0.0
    is_available: bool = True
    current_job_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "device_id": self.device_id,
            "name": self.name,
            "is_available": self.is_available,
            "memory_used_mb": self.memory_used_mb,
            "memory_total_mb": self.memory_total_mb,
            "temperature_celsius": self.temperature_celsius,
            "utilization_percent": self.utilization_percent,
            "current_job_id": self.current_job_id
        }
