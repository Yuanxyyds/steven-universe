"""
Shared Pydantic schemas for GPU Service API contracts.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class TaskType(str, Enum):
    """Type of task execution."""
    # ONEOFF = "oneoff"    # REMOVED - all tasks now session-based
    SESSION = "session"    # Long-lived session, container persists


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkerStatus(str, Enum):
    """Worker container lifecycle status (applies to both oneoff and session workers)."""
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
    CONNECTED = "connected"        # Connection established, GPU allocated
    TEXT_DELTA = "text_delta"      # Streaming text output (chunk)
    TEXT = "text"                  # Final complete text output
    LOGS = "logs"                  # Debug/info/worker status logs
    COMPLETED = "completed"        # Task completion


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
    model_id: Optional[str] = Field(
        default=None,
        description="Override model identifier (e.g., 'meta-llama/Llama-3.1-8B-Instruct')"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific parameters merged with task definition defaults"
    )


@dataclass
class StreamEvent:
    """
    Single event in SSE stream.

    Provides type-safe serialization and deserialization for SSE events
    used in worker communication.
    """

    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_sse_format(self) -> str:
        """
        Convert to Server-Sent Events format.

        Returns:
            SSE-formatted string
        """
        import json
        return f"event: {self.event_type.value}\ndata: {json.dumps(self.data)}\n\n"

    @classmethod
    def from_sse(cls, event_type_str: str, data_json: str) -> "StreamEvent":
        """
        Create StreamEvent from SSE event type and data.

        Args:
            event_type_str: Event type string (e.g., "logs", "text_delta")
            data_json: JSON string of event data

        Returns:
            StreamEvent instance

        Raises:
            ValueError: If event type is invalid or data cannot be parsed
        """
        import json

        # Parse data JSON
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {e}")

        # Map event type string to enum
        event_type = None
        for et in EventType:
            if et.value == event_type_str:
                event_type = et
                break

        if not event_type:
            raise ValueError(f"Unknown event type: {event_type_str}")

        return cls(event_type=event_type, data=data)

    @classmethod
    def connected(
        cls,
        status: str,
        gpu_id: Optional[int] = None,
        session_id: Optional[str] = None,
        message: Optional[str] = None
    ) -> "StreamEvent":
        """Create CONNECTED event."""
        data = {"status": status}
        if gpu_id is not None:
            data["gpu_id"] = gpu_id
        if session_id:
            data["session_id"] = session_id
        if message:
            data["message"] = message

        return cls(event_type=EventType.CONNECTED, data=data)

    @classmethod
    def text_delta(cls, delta: str) -> "StreamEvent":
        """Create TEXT_DELTA event."""
        return cls(event_type=EventType.TEXT_DELTA, data={"delta": delta})

    @classmethod
    def text(cls, content: str) -> "StreamEvent":
        """Create TEXT event."""
        return cls(event_type=EventType.TEXT, data={"content": content})

    @classmethod
    def logs(
        cls,
        log: str,
        level: str = "info",
        timestamp: Optional[str] = None
    ) -> "StreamEvent":
        """Create LOGS event."""
        data = {"log": log, "level": level}
        if timestamp:
            data["timestamp"] = timestamp

        return cls(event_type=EventType.LOGS, data=data)

    @classmethod
    def completed(
        cls,
        status: str,
        elapsed_seconds: Optional[int] = None,
        error: Optional[str] = None,
        **extra_data
    ) -> "StreamEvent":
        """Create COMPLETED event with optional extra data."""
        data = {"status": status}
        if elapsed_seconds is not None:
            data["elapsed_seconds"] = elapsed_seconds
        if error:
            data["error"] = error
        # Allow extra fields like countdown_steps
        data.update(extra_data)

        return cls(event_type=EventType.COMPLETED, data=data)


class SessionResponse(BaseModel):
    """Session information."""
    session_id: str
    status: WorkerStatus
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
