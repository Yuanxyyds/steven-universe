"""
Job data models and state management.
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from shared_schemas.gpu_service import JobStatus, JobType


@dataclass
class Job:
    """Represents a GPU job."""
    job_id: str
    job_type: JobType
    docker_image: str
    command: List[str]
    env_vars: Dict[str, str]
    timeout_seconds: int
    priority: int
    model_id: Optional[str]
    volume_mounts: Dict[str, str]
    status: JobStatus = JobStatus.PENDING
    gpu_device_id: Optional[int] = None
    container_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    recent_logs: List[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        job_type: JobType,
        docker_image: str,
        command: List[str],
        env_vars: Dict[str, str],
        timeout_seconds: int,
        priority: int,
        model_id: Optional[str] = None,
        volume_mounts: Optional[Dict[str, str]] = None
    ) -> "Job":
        """Create a new job with generated ID."""
        return cls(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            docker_image=docker_image,
            command=command,
            env_vars=env_vars,
            timeout_seconds=timeout_seconds,
            priority=priority,
            model_id=model_id,
            volume_mounts=volume_mounts or {}
        )

    @property
    def elapsed_seconds(self) -> Optional[int]:
        """Calculate elapsed time in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return int((end_time - self.started_at).total_seconds())

    def to_response_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "job_type": self.job_type.value,
            "docker_image": self.docker_image,
            "command": self.command,
            "gpu_device_id": self.gpu_device_id,
            "container_id": self.container_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": self.elapsed_seconds,
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority,
            "error_message": self.error_message,
            "recent_logs": self.recent_logs[-10:]  # Last 10 log lines
        }
