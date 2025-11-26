"""
Session data models for internal use.
"""

import uuid
import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from shared_schemas.gpu_service import SessionStatus


@dataclass
class Session:
    """Represents a long-lived GPU session."""

    session_id: str
    container_id: str
    gpu_device_id: int
    model_id: str
    task_difficulty: str

    # Status
    status: SessionStatus = SessionStatus.INITIALIZING

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)

    # Lifecycle limits
    idle_timeout_seconds: int = 300  # 5 minutes
    max_lifetime_seconds: int = 3600  # 1 hour

    # Request queue (FIFO, max 3-5 requests)
    request_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=5))

    # Metadata
    current_task_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        container_id: str,
        gpu_device_id: int,
        model_id: str,
        task_difficulty: str,
        idle_timeout_seconds: int = 300,
        max_lifetime_seconds: int = 3600
    ) -> "Session":
        """
        Create a new session.

        Args:
            container_id: Docker container ID
            gpu_device_id: Allocated GPU device ID
            model_id: Model identifier
            task_difficulty: Task difficulty level
            idle_timeout_seconds: Idle timeout
            max_lifetime_seconds: Max lifetime

        Returns:
            New Session instance
        """
        return cls(
            session_id=str(uuid.uuid4()),
            container_id=container_id,
            gpu_device_id=gpu_device_id,
            model_id=model_id,
            task_difficulty=task_difficulty,
            idle_timeout_seconds=idle_timeout_seconds,
            max_lifetime_seconds=max_lifetime_seconds
        )

    def mark_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def is_idle_timeout_exceeded(self) -> bool:
        """Check if session has been idle too long."""
        if self.status != SessionStatus.WAITING:
            return False
        idle_time = (datetime.utcnow() - self.last_activity).total_seconds()
        return idle_time > self.idle_timeout_seconds

    def is_max_lifetime_exceeded(self) -> bool:
        """Check if session has exceeded max lifetime."""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.max_lifetime_seconds

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self.request_queue.qsize()

    @property
    def is_queue_full(self) -> bool:
        """Check if request queue is full."""
        return self.request_queue.full()

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "gpu_device_id": self.gpu_device_id,
            "container_id": self.container_id,
            "model_id": self.model_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "queue_size": self.queue_size,
            "current_task_id": self.current_task_id
        }
