"""
Task data models for internal use.
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from shared_schemas.gpu_service import TaskType, TaskStatus, TaskDifficulty


@dataclass
class TaskDefinition:
    """Pre-defined task template configuration."""
    task_name: str
    description: str
    task_type: str  # "session" only (oneoff removed)
    task_difficulty: str  # "low" or "high"
    timeout_seconds: int
    idle_timeout_seconds: int  # How long session can be idle before termination
    metadata: Dict[str, Any]
    model_id: Optional[str] = None  # Optional for non-LLM tasks
    scheduler_type: str = "centralized"  # "centralized" or "distributed"


@dataclass
class TaskAction:
    """Worker execution configuration for a task."""
    task_name: str
    source_path: str
    dockerfile: str
    docker_image: str
    command: List[str]
    env_vars: Dict[str, str]
    build_args: Dict[str, str]
    worker_client_path: str  # Import path to worker client class


@dataclass
class ModelPath:
    """Model filesystem path configuration."""
    model_id: str
    path: str
    description: str
    size_gb: float


@dataclass
class Task:
    """
    Represents a single task within a session.

    Configuration data is stored in task_definition, task_action, and model_path.
    This class tracks runtime state and execution metadata.
    """

    # Unique identifier
    task_id: str

    # Configuration objects (contain task_type, difficulty, model_id, metadata, etc.)
    task_definition: TaskDefinition
    task_action: TaskAction
    model_path: Optional[ModelPath] = None

    # Runtime status tracking
    status: TaskStatus = TaskStatus.PENDING
    session_id: Optional[str] = None
    container_id: Optional[str] = None
    gpu_id: Optional[int] = None

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
        task_definition: TaskDefinition,
        task_action: TaskAction,
        model_path: Optional[ModelPath] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> "Task":
        """
        Create a new task from configuration objects.

        Args:
            task_definition: Task configuration from YAML
            task_action: Task action configuration from YAML
            model_path: Optional model path configuration
            task_id: Optional task ID (generates UUID if not provided)
            session_id: Optional session ID (for session tasks)

        Returns:
            New Task instance
        """
        return cls(
            task_id=task_id or str(uuid.uuid4()),
            task_definition=task_definition,
            task_action=task_action,
            model_path=model_path,
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
            "task_type": self.task_definition.task_type,
            "task_difficulty": self.task_definition.task_difficulty,
            "task_name": self.task_definition.task_name,
            "model_id": self.task_definition.model_id,
            "session_id": self.session_id,
            "container_id": self.container_id,
            "gpu_id": self.gpu_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": self.elapsed_seconds,
            "timeout_seconds": self.task_definition.timeout_seconds,
            "error_message": self.error_message,
            "recent_logs": self.recent_logs[-10:]  # Last 10 log lines
        }
