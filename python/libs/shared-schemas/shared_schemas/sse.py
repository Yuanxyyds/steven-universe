"""
Shared SSE (Server-Sent Events) schemas.
Used across multiple services: web-server, gpu-service, worker, stevenai-service.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass


class EventType(str, Enum):
    """Streaming event types for SSE."""
    CONNECTED = "connected"        # Connection established, GPU allocated
    TEXT_DELTA = "text_delta"      # Streaming text output (chunk)
    TEXT = "text"                  # Final complete text output
    LOGS = "logs"                  # Debug/info/worker status logs
    COMPLETED = "completed"        # Task completion


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

    def to_dict(self) -> str:
        """
        Convert to JSON string for EventSourceResponse.

        EventSourceResponse expects either strings or dicts with specific keys
        (data, event, id, retry). We serialize to JSON string which becomes
        the SSE data field.

        Returns:
            JSON string with event_type and all data fields
        """
        import json
        return json.dumps({
            "event_type": self.event_type.value,
            **self.data
        })

    @classmethod
    def from_dict(cls, data: dict) -> "StreamEvent":
        """
        Create StreamEvent from dict (from EventSourceResponse format).

        Expects dict with "event_type" field and other data fields.

        Args:
            data: Dict with event_type and data fields

        Returns:
            StreamEvent instance

        Raises:
            ValueError: If event_type is invalid
        """
        event_type_str = data.get("event_type")
        if not event_type_str:
            raise ValueError("Missing event_type in data")

        # Map event type string to enum
        event_type = None
        for et in EventType:
            if et.value == event_type_str:
                event_type = et
                break

        if not event_type:
            raise ValueError(f"Unknown event type: {event_type_str}")

        # Extract data (everything except event_type)
        event_data = {k: v for k, v in data.items() if k != "event_type"}

        return cls(event_type=event_type, data=event_data)

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
