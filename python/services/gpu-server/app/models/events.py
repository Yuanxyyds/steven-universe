"""
Event models for streaming responses.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from shared_schemas.gpu_service import EventType


@dataclass
class StreamEvent:
    """Single event in SSE stream."""

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
    def connection(
        cls,
        status: str,
        gpu_id: Optional[int] = None,
        session_id: Optional[str] = None,
        message: Optional[str] = None
    ) -> "StreamEvent":
        """Create CONNECTION event."""
        data = {"status": status}
        if gpu_id is not None:
            data["gpu_id"] = gpu_id
        if session_id:
            data["session_id"] = session_id
        if message:
            data["message"] = message

        return cls(event_type=EventType.CONNECTION, data=data)

    @classmethod
    def worker(
        cls,
        status: str,
        container_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> "StreamEvent":
        """Create WORKER event."""
        data = {"status": status}
        if container_id:
            data["container_id"] = container_id
        if error:
            data["error"] = error

        return cls(event_type=EventType.WORKER, data=data)

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
    def task_finish(
        cls,
        status: str,
        elapsed_seconds: Optional[int] = None,
        error: Optional[str] = None
    ) -> "StreamEvent":
        """Create TASK_FINISH event."""
        data = {"status": status}
        if elapsed_seconds is not None:
            data["elapsed_seconds"] = elapsed_seconds
        if error:
            data["error"] = error

        return cls(event_type=EventType.TASK_FINISH, data=data)


class EventParser:
    """Parse docker logs into structured events."""

    @staticmethod
    def parse_log_line(line: str) -> Optional[StreamEvent]:
        """
        Parse a single log line into an event.

        Tries to parse as JSON first. If successful, extracts event type.
        If not JSON, treats as plain log.

        Args:
            line: Single line from docker logs

        Returns:
            StreamEvent if parseable, None if empty/invalid
        """
        import json

        line = line.strip()
        if not line:
            return None

        try:
            # Try to parse as JSON
            data = json.loads(line)

            if isinstance(data, dict) and "type" in data:
                # Structured event from worker
                event_type_str = data.get("type")
                event_data = data.get("data", {})

                # Map type string to EventType enum
                event_type = None
                for et in EventType:
                    if et.value == event_type_str:
                        event_type = et
                        break

                if event_type:
                    return StreamEvent(event_type=event_type, data=event_data)

        except json.JSONDecodeError:
            pass

        # Fallback: Treat as plain log
        return StreamEvent.logs(log=line, level="info")
