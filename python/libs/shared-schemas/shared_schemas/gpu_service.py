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


class JobType(str, Enum):
    """Type of GPU job/workload."""
    INFERENCE = "inference"
    TRAINING = "training"
    PREPROCESSING = "preprocessing"
    CUSTOM = "custom"


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

class TaskSubmitRequest(BaseModel):
    """Request to submit a new task."""
    # Session control
    task_type: TaskType = Field(..., description="Task type: oneoff or session")
    session_id: Optional[str] = Field(default=None, description="Existing session ID to reuse")
    create_session: bool = Field(default=False, description="Create new session for this task")

    # Task configuration
    task_difficulty: TaskDifficulty = Field(..., description="Computational difficulty: low or high")
    model_id: str = Field(..., description="Model identifier (e.g., 'llama-7b', 'stable-diffusion-xl')")
    task_preset: str = Field(..., description="Task preset (e.g., 'inference', 'training')")

    # Task-specific parameters (flexible for different task types)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific parameters (e.g., prompt, max_tokens, temperature)"
    )

    # Execution limits
    timeout_seconds: int = Field(default=300, ge=10, le=1800, description="Task timeout in seconds")


class TaskSubmitResponse(BaseModel):
    """Response immediately after task submission (before streaming starts)."""
    task_id: str = Field(..., description="Server-generated task ID (UUID)")
    session_id: str = Field(..., description="Session ID (new or existing)")
    status: str = Field(..., description="Initial status: processing, queued, or rejected")


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


# ============================================================================
# Legacy Models (for backward compatibility - can be deprecated later)
# ============================================================================

class JobStatus(str, Enum):
    """Legacy job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSubmitRequest(BaseModel):
    """Legacy request to submit a new GPU job."""
    job_type: JobType = JobType.INFERENCE
    docker_image: str = Field(..., description="Docker image to run")
    command: List[str] = Field(..., description="Command to execute in container")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    timeout_seconds: int = Field(default=3600, ge=60, le=86400, description="Job timeout")
    priority: int = Field(default=5, ge=1, le=10, description="Job priority (1=lowest, 10=highest)")
    model_id: Optional[str] = Field(default=None, description="Model ID to fetch from file-service")
    volume_mounts: Dict[str, str] = Field(default_factory=dict, description="Additional volume mounts")


class JobSubmitResponse(BaseModel):
    """Legacy response after submitting a job."""
    success: bool
    job_id: str
    status: JobStatus
    created_at: datetime
    estimated_wait_time_seconds: Optional[int] = None
    message: Optional[str] = None


class JobResponse(BaseModel):
    """Legacy detailed job information."""
    job_id: str
    status: JobStatus
    job_type: JobType
    docker_image: str
    command: List[str]
    gpu_device_id: Optional[int] = None
    container_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    elapsed_seconds: Optional[int] = None
    timeout_seconds: int
    priority: int
    error_message: Optional[str] = None
    recent_logs: List[str] = Field(default_factory=list)
