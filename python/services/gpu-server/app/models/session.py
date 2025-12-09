"""
Session data models for internal use.
"""

import uuid
import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from shared_schemas.gpu_service import WorkerStatus


@dataclass
class Session:
    """Represents a long-lived GPU session."""

    session_id: str
    container_id: str
    gpu_device_id: int
    model_id: str
    task_difficulty: str

    # Optional: predefined task name (for session reuse optimization)
    predefined_task_name: Optional[str] = None

    # Scheduler type (centralized or distributed)
    scheduler_type: str = "centralized"

    # Status
    status: WorkerStatus = WorkerStatus.INITIALIZING

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)

    # Lifecycle limits
    idle_timeout_seconds: int = 300  # 5 minutes
    max_lifetime_seconds: int = 3600  # 1 hour

    # Request queue (FIFO, max 3-5 requests)
    request_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=5))

    # Task completion events (task_id -> Event)
    _task_events: dict = field(default_factory=dict)

    # Ready event - signaled when worker is ready (health check passes)
    _ready_event: Optional[asyncio.Event] = None

    # Metadata
    current_task_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        container_id: str,
        gpu_device_id: int,
        model_id: str,
        task_difficulty: str,
        predefined_task_name: Optional[str] = None,
        scheduler_type: str = "centralized",
        idle_timeout_seconds: int = 300,
        max_lifetime_seconds: int = 3600,
        session_id: Optional[str] = None
    ) -> "Session":
        """
        Create a new session.

        Args:
            container_id: Docker container ID
            gpu_device_id: Allocated GPU device ID
            model_id: Model identifier
            task_difficulty: Task difficulty level
            predefined_task_name: Optional predefined task name (for session reuse)
            scheduler_type: Scheduler type (centralized or distributed)
            idle_timeout_seconds: Idle timeout
            max_lifetime_seconds: Max lifetime
            session_id: Optional pre-generated session ID (if None, generates new UUID)

        Returns:
            New Session instance
        """
        return cls(
            session_id=session_id if session_id else str(uuid.uuid4()),
            container_id=container_id,
            gpu_device_id=gpu_device_id,
            model_id=model_id,
            task_difficulty=task_difficulty,
            predefined_task_name=predefined_task_name,
            scheduler_type=scheduler_type,
            idle_timeout_seconds=idle_timeout_seconds,
            max_lifetime_seconds=max_lifetime_seconds
        )

    def mark_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def is_idle_timeout_exceeded(self) -> bool:
        """Check if session has been idle too long."""
        if self.status == WorkerStatus.WORKING:
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

    def create_task_event(self, task_id: str) -> asyncio.Event:
        """Create an event for a task to wait on."""
        event = asyncio.Event()
        self._task_events[task_id] = event
        return event

    def get_task_event(self, task_id: str) -> Optional[asyncio.Event]:
        """Get the event for a task."""
        return self._task_events.get(task_id)

    def complete_task(self, task_id: str):
        """Mark a task as completed and signal its event."""
        event = self._task_events.pop(task_id, None)
        if event:
            event.set()

    def create_ready_event(self) -> asyncio.Event:
        """Create ready event for waiting on worker health check."""
        self._ready_event = asyncio.Event()
        return self._ready_event

    def get_ready_event(self) -> Optional[asyncio.Event]:
        """Get the ready event."""
        return self._ready_event

    def signal_ready(self):
        """Signal that worker is ready (health check passed)."""
        if self._ready_event:
            self._ready_event.set()

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "gpu_device_id": self.gpu_device_id,
            "container_id": self.container_id,
            "model_id": self.model_id,
            "predefined_task_name": self.predefined_task_name,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "queue_size": self.queue_size,
            "current_task_id": self.current_task_id
        }
