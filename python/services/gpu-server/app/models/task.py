"""
Task data models for internal use.
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from shared_schemas.gpu_service import TaskType, TaskStatus, TaskDifficulty


@dataclass
class Task:
    """Represents a single task (within a session or one-off)."""

    task_id: str
    task_type: TaskType
    task_difficulty: TaskDifficulty
    model_id: str
    task_preset: str
    metadata: Dict[str, Any]
    timeout_seconds: int

    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    session_id: Optional[str] = None
    container_id: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results and errors
    error_message: Optional[str] = None
    recent_logs: list = field(default_factory=list)

    @classmethod
    def create(
        cls,
        task_type: TaskType,
        task_difficulty: TaskDifficulty,
        model_id: str,
        task_preset: str,
        metadata: Dict[str, Any],
        timeout_seconds: int,
        session_id: Optional[str] = None
    ) -> "Task":
        """
        Create a new task with generated ID.

        Args:
            task_type: Task type (oneoff or session)
            task_difficulty: Task difficulty (low or high)
            model_id: Model identifier
            task_preset: Task preset name
            metadata: Task-specific parameters
            timeout_seconds: Task timeout
            session_id: Existing session ID (if reusing)

        Returns:
            New Task instance
        """
        return cls(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            task_difficulty=task_difficulty,
            model_id=model_id,
            task_preset=task_preset,
            metadata=metadata,
            timeout_seconds=timeout_seconds,
            session_id=session_id
        )

    @property
    def elapsed_seconds(self) -> Optional[int]:
        """Calculate elapsed time in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return int((end_time - self.started_at).total_seconds())

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "task_type": self.task_type.value,
            "task_difficulty": self.task_difficulty.value,
            "model_id": self.model_id,
            "task_preset": self.task_preset,
            "session_id": self.session_id,
            "container_id": self.container_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": self.elapsed_seconds,
            "timeout_seconds": self.timeout_seconds,
            "error_message": self.error_message,
            "recent_logs": self.recent_logs[-10:]  # Last 10 log lines
        }
