"""
Session Manager - Manages session lifecycle, routing, and timeouts.

Handles:
- Session creation and destruction
- Session state management (INITIALIZING, WAITING, WORKING, KILLED)
- Idle timeout and max lifetime monitoring
- Model matching (reuse IDLE sessions with same model)
- Per-session FIFO request queues
"""

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime

from app.models.session import Session
from app.models.task import Task
from app.core.config import settings
from app.core.manager.gpu_manager import gpu_manager
from shared_schemas.gpu_service import SessionStatus

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages GPU sessions with timeout monitoring and model reuse optimization.
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize session manager and start monitoring."""
        if self._initialized:
            return

        logger.info("Initializing Session Manager...")
        self._initialized = True

        # Start background timeout monitor
        self._monitor_task = asyncio.create_task(self._monitor_timeouts_loop())
        logger.info("Session Manager initialized")

    async def shutdown(self):
        """Shutdown session manager and cleanup resources."""
        logger.info("Shutting down Session Manager...")

        # Cancel monitor task
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Kill all active sessions
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.kill_session(session_id, reason="shutdown")

        self._initialized = False
        logger.info("Session Manager shutdown complete")

    async def create_session(
        self,
        container_id: str,
        gpu_device_id: int,
        model_id: str,
        task_difficulty: str
    ) -> Session:
        """
        Create a new session.

        Args:
            container_id: Docker container ID
            gpu_device_id: Allocated GPU device ID
            model_id: Model identifier
            task_difficulty: Task difficulty level

        Returns:
            Created Session instance
        """
        async with self._lock:
            session = Session.create(
                container_id=container_id,
                gpu_device_id=gpu_device_id,
                model_id=model_id,
                task_difficulty=task_difficulty,
                idle_timeout_seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS,
                max_lifetime_seconds=settings.SESSION_MAX_LIFETIME_SECONDS
            )

            self._sessions[session.session_id] = session
            logger.info(f"Created session {session.session_id} on GPU {gpu_device_id} for model {model_id}")

            return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found, None otherwise
        """
        return self._sessions.get(session_id)

    async def find_idle_session_with_model(self, model_id: str) -> Optional[Session]:
        """
        Find an IDLE session with matching model (model reuse optimization).

        Args:
            model_id: Model identifier to match

        Returns:
            Session if found, None otherwise
        """
        async with self._lock:
            for session in self._sessions.values():
                if (session.status == SessionStatus.WAITING and
                    session.model_id == model_id and
                    not session.is_queue_full):
                    logger.info(f"Found idle session {session.session_id} for model {model_id} (reuse optimization)")
                    return session

            return None

    async def enqueue_request(self, session_id: str, task: Task) -> bool:
        """
        Add request to session's FIFO queue.

        Args:
            session_id: Session identifier
            task: Task to enqueue

        Returns:
            True if enqueued, False if queue is full
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for enqueue")
            return False

        if session.is_queue_full:
            logger.warning(f"Session {session_id} queue is full (max={settings.SESSION_QUEUE_MAX_SIZE})")
            return False

        try:
            await session.request_queue.put(task)
            session.mark_activity()
            logger.info(f"Enqueued task {task.task_id} to session {session_id} (queue_size={session.queue_size})")
            return True
        except asyncio.QueueFull:
            logger.error(f"Session {session_id} queue unexpectedly full")
            return False

    async def dequeue_request(self, session_id: str, timeout: float = None) -> Optional[Task]:
        """
        Dequeue next request from session's FIFO queue.

        Args:
            session_id: Session identifier
            timeout: Optional timeout in seconds

        Returns:
            Task if available, None if queue empty or timeout
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        try:
            task = await asyncio.wait_for(
                session.request_queue.get(),
                timeout=timeout
            )
            logger.info(f"Dequeued task {task.task_id} from session {session_id}")
            return task
        except asyncio.TimeoutError:
            return None

    async def mark_activity(self, session_id: str):
        """
        Update session last activity timestamp.

        Args:
            session_id: Session identifier
        """
        session = await self.get_session(session_id)
        if session:
            session.mark_activity()

    async def update_session_status(self, session_id: str, status: SessionStatus):
        """
        Update session status.

        Args:
            session_id: Session identifier
            status: New status
        """
        session = await self.get_session(session_id)
        if session:
            old_status = session.status
            session.status = status
            logger.info(f"Session {session_id} status: {old_status.value} → {status.value}")

    async def kill_session(self, session_id: str, reason: str = "manual"):
        """
        Kill session and release resources.

        Args:
            session_id: Session identifier
            reason: Reason for killing (idle_timeout, max_lifetime, error, manual, shutdown)
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"Attempted to kill non-existent session {session_id}")
                return

            logger.info(f"Killing session {session_id} (reason={reason})")

            # Update status
            session.status = SessionStatus.KILLED

            # Release GPU
            await gpu_manager.release_gpu(session.gpu_device_id)

            # TODO: Stop Docker container via Docker Manager

            # Remove from tracking
            del self._sessions[session_id]

            logger.info(f"Session {session_id} killed and resources released")

    async def get_all_sessions(self) -> List[Session]:
        """
        Get all active sessions.

        Returns:
            List of Session objects
        """
        return list(self._sessions.values())

    async def get_session_count(self) -> int:
        """
        Get count of active sessions.

        Returns:
            Number of active sessions
        """
        return len(self._sessions)

    async def _monitor_timeouts_loop(self):
        """Background task to monitor session timeouts."""
        logger.info(f"Starting session timeout monitor (interval={settings.SESSION_MONITOR_INTERVAL}s)")

        while True:
            try:
                await asyncio.sleep(settings.SESSION_MONITOR_INTERVAL)
                await self._check_timeouts()
            except asyncio.CancelledError:
                logger.info("Session timeout monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in session timeout monitor: {e}", exc_info=True)

    async def _check_timeouts(self):
        """Check all sessions for timeouts and kill expired ones."""
        now = datetime.utcnow()
        sessions_to_kill = []

        # Collect sessions to kill (don't modify dict during iteration)
        for session_id, session in self._sessions.items():
            # Check max lifetime
            if session.is_max_lifetime_exceeded():
                sessions_to_kill.append((session_id, "max_lifetime"))
                continue

            # Check idle timeout (only for WAITING status)
            if session.is_idle_timeout_exceeded():
                sessions_to_kill.append((session_id, "idle_timeout"))

        # Kill sessions
        for session_id, reason in sessions_to_kill:
            await self.kill_session(session_id, reason=reason)

        if sessions_to_kill:
            logger.info(f"Killed {len(sessions_to_kill)} sessions due to timeout")


# Global session manager instance
session_manager = SessionManager()
