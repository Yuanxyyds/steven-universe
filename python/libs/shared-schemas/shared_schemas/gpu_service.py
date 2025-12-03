"""
Shared Pydantic schemas for GPU Service API contracts.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class TaskType(str, Enum):
    """Type of task execution."""
    ONEOFF = "oneoff"      # One-time task, container killed after completion
    SESSION = "session"    # Long-lived session, container persists


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionStatus(str, Enum):
    """Session lifecycle status."""
    INITIALIZING = "initializing"  # Container starting, model loading
    WAITING = "waiting"            # Idle, ready for requests
    WORKING = "working"            # Processing a request
    KILLED = "killed"              # Terminated


class TaskDifficulty(str, Enum):
    """Task computational difficulty level for GPU routing."""
    LOW = "low"    # Use regular GPU
    HIGH = "high"  # Use high-power GPU


class EventType(str, Enum):
    """Streaming event types for SSE."""
    CONNECTION = "connection"      # GPU allocation status
    WORKER = "worker"              # Worker container status
    TEXT_DELTA = "text_delta"      # Streaming text piece
    TEXT = "text"                  # Final complete text
    LOGS = "logs"                  # Debug/info logs
    TASK_FINISH = "task_finish"    # Task completion


# ============================================================================
# Request/Response Models
# ============================================================================

class PreDefinedTaskRequest(BaseModel):
    """
    Request for pre-defined task execution.

    All pre-defined tasks must specify a task_name which maps to configuration
    in task_definitions.yaml. Other fields are optional overrides.
    """
    task_name: str = Field(
        ...,
        description="Pre-defined task name (required, e.g., 'loading-test')"
    )

    # Optional overrides for task definition defaults
    task_difficulty: Optional[TaskDifficulty] = Field(
        default=None,
        description="Override task difficulty: low or high"
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        ge=10,
        le=1800,
        description="Override task timeout in seconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific parameters merged with task definition defaults"
    )

    # Session control (for future session support)
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session ID to reuse (for session tasks)"
    )
    create_session: bool = Field(
        default=False,
        description="Create new session for this task (for session tasks)"
    )


class CustomTaskRequest(BaseModel):
    """
    Request for custom task execution (TODO).

    Placeholder for future implementation where users can specify
    arbitrary docker images, commands, and configurations.
    """
    pass


class StreamEvent(BaseModel):
    """Single event in SSE stream."""
    event: EventType = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event payload")


class SessionResponse(BaseModel):
    """Session information."""
    session_id: str
    status: SessionStatus
    gpu_device_id: int
    container_id: str
    model_id: Optional[str] = None
    created_at: datetime
    last_activity: datetime
    queue_size: int = Field(..., description="Number of requests currently queued")


class SessionListResponse(BaseModel):
    """List of active sessions."""
    sessions: List[SessionResponse]
    total: int


# ============================================================================
# GPU Status Models
# ============================================================================

class GPUStatus(BaseModel):
    """Single GPU device status."""
    device_id: int
    name: str
    difficulty: str = Field(..., description="GPU difficulty level: low or high")
    is_available: bool
    memory_used_mb: int
    memory_total_mb: int
    temperature_celsius: float
    utilization_percent: float
    current_session_id: Optional[str] = Field(default=None, description="Active session using this GPU")


class HealthResponse(BaseModel):
    """GPU service health status."""
    status: str = Field(..., description="Service status: healthy, degraded, unhealthy")
    service: str = "GPU Service"
    version: str
    gpus: List[GPUStatus]
    active_sessions: int = Field(..., description="Number of active sessions")
    active_tasks: int = Field(..., description="Number of currently processing tasks")
