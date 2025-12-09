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

from app.models.session import Session
from app.models.task import Task
from app.core.config import settings
from app.core.manager.gpu_manager import gpu_manager
from app.core.manager.docker_manager import docker_manager
from shared_schemas.gpu_service import WorkerStatus

logger = logging.getLogger(__name__)


class SessionDispatcher:
    """
    Global dispatcher for all sessions.

    Runs periodic checks for:
    1. Timeout monitoring (idle timeout, max lifetime)
    2. Queue dispatch (process queued tasks for WAITING sessions)
    3. Cleanup (remove dead sessions)
    """

    def __init__(self, session_manager: 'SessionManager'):
        self.session_manager = session_manager
        self._dispatch_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start dispatcher background task."""
        if self._running:
            return

        self._running = True
        logger.info("Starting SessionDispatcher...")

        # Start single dispatcher loop
        self._dispatch_task = asyncio.create_task(self._dispatcher_loop())

        logger.info("SessionDispatcher started")

    async def stop(self):
        """Stop dispatcher background task."""
        logger.info("Stopping SessionDispatcher...")
        self._running = False

        # Cancel dispatch task
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        logger.info("SessionDispatcher stopped")

    async def _dispatcher_loop(self):
        """
        Main dispatcher loop that checks all sessions periodically.

        Performs:
        1. Timeout monitoring (check idle timeout and max lifetime)
        2. Queue dispatch (process queued tasks for WAITING sessions)
        """
        logger.info(f"Dispatcher loop started (interval={settings.SESSION_MONITOR_INTERVAL}s)")

        while self._running:
            try:
                # 1. Check timeouts and kill expired sessions
                await self._check_timeouts()

                # 2. Dispatch queued tasks for WAITING sessions
                await self._dispatch_queued_tasks()

                # Sleep until next check
                await asyncio.sleep(settings.SESSION_MONITOR_INTERVAL)

            except asyncio.CancelledError:
                logger.info("Dispatcher loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in dispatcher loop: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("Dispatcher loop stopped")

    async def _check_timeouts(self):
        """Check all sessions for timeouts and kill expired ones."""
        sessions_to_kill = []

        # Collect sessions to kill (don't modify dict during iteration)
        for session_id, session in self.session_manager._sessions.items():
            # Check max lifetime
            if session.is_max_lifetime_exceeded():
                sessions_to_kill.append((session_id, "max_lifetime"))
                continue

            # Check idle timeout (only for WAITING status)
            if session.is_idle_timeout_exceeded():
                sessions_to_kill.append((session_id, "idle_timeout"))

        # Kill sessions
        for session_id, reason in sessions_to_kill:
            await self.session_manager.kill_session(session_id, reason=reason)

        if sessions_to_kill:
            logger.info(f"Killed {len(sessions_to_kill)} sessions due to timeout")

    async def _dispatch_queued_tasks(self):
        """
        Dispatch queued tasks for all WAITING sessions.

        For centralized scheduling:
        - Dequeue one task at a time
        - Mark session as WORKING
        - Signal handler to process

        For distributed scheduling:
        - Dequeue and signal immediately
        - Keep session in WAITING (worker manages internal queue)
        """
        for session_id, session in list(self.session_manager._sessions.items()):
            try:
                # Only dispatch if session is WAITING (ready for work)
                if session.status != WorkerStatus.WAITING:
                    continue

                # Check if there are queued tasks (non-blocking)
                if session.queue_size == 0:
                    continue

                # Dequeue next task (non-blocking)
                try:
                    task = session.request_queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue

                # Mark session activity
                session.mark_activity()

                # Update session status based on scheduler type
                if session.scheduler_type == "centralized":
                    # Centralized: Mark as WORKING (one task at a time)
                    session.current_task_id = task.task_id
                    await self.session_manager.update_session_status(session_id, WorkerStatus.WORKING)
                    logger.info(f"Dequeued task {task.task_id} for centralized session {session_id}, signaling handler")
                else:
                    # Distributed: Keep WAITING (worker manages queue)
                    logger.info(f"Dequeued task {task.task_id} for distributed session {session_id}, signaling handler")

                # Signal the task event - handler will continue processing
                # Handler is responsible for:
                # 1. Sending task to worker
                # 2. Streaming SSE responses
                # 3. Completing the task
                # 4. (Centralized only) Updating session status back to WAITING
                event = session.get_task_event(task.task_id)
                if event:
                    event.set()
                else:
                    logger.warning(f"No event found for task {task.task_id}, marking complete")
                    session.complete_task(task.task_id)
                    if session.scheduler_type == "centralized":
                        await self.session_manager.update_session_status(session_id, WorkerStatus.WAITING)
                        session.current_task_id = None

            except Exception as e:
                logger.error(f"Error dispatching task for session {session_id}: {e}", exc_info=True)
                # On error, reset session to WAITING (centralized only)
                if session_id in self.session_manager._sessions:
                    session = self.session_manager._sessions[session_id]
                    if session.scheduler_type == "centralized":
                        await self.session_manager.update_session_status(session_id, WorkerStatus.WAITING)
                        session.current_task_id = None


class SessionManager:
    """
    Manages GPU sessions with timeout monitoring and model reuse optimization.
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._dispatcher = SessionDispatcher(self)

    async def initialize(self):
        """Initialize session manager and start dispatcher."""
        if self._initialized:
            return

        logger.info("Initializing Session Manager...")
        self._initialized = True

        # Start dispatcher
        await self._dispatcher.start()
        logger.info("Session Manager initialized")

    async def shutdown(self):
        """Shutdown session manager and cleanup resources."""
        logger.info("Shutting down Session Manager...")

        # Stop dispatcher
        await self._dispatcher.stop()

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
        task_difficulty: str,
        predefined_task_name: Optional[str] = None,
        scheduler_type: str = "centralized",
        session_id: Optional[str] = None
    ) -> Session:
        """
        Create a new session.

        Args:
            container_id: Docker container ID
            gpu_device_id: Allocated GPU device ID
            model_id: Model identifier
            task_difficulty: Task difficulty level
            predefined_task_name: Optional predefined task name (for session reuse)
            scheduler_type: Scheduler type (centralized or distributed)
            session_id: Optional pre-generated session ID (if None, Session.create generates one)

        Returns:
            Created Session instance
        """
        async with self._lock:
            session = Session.create(
                container_id=container_id,
                gpu_device_id=gpu_device_id,
                model_id=model_id,
                task_difficulty=task_difficulty,
                predefined_task_name=predefined_task_name,
                scheduler_type=scheduler_type,
                idle_timeout_seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS,
                max_lifetime_seconds=settings.SESSION_MAX_LIFETIME_SECONDS,
                session_id=session_id
            )

            self._sessions[session.session_id] = session

            task_info = f"predefined task '{predefined_task_name}'" if predefined_task_name else "custom task"
            logger.info(
                f"Created session {session.session_id} on GPU {gpu_device_id} "
                f"for model {model_id} ({task_info})"
            )

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
                if (session.status == WorkerStatus.WAITING and
                    session.model_id == model_id and
                    not session.is_queue_full):
                    logger.info(f"Found idle session {session.session_id} for model {model_id} (reuse optimization)")
                    return session

            return None

    async def find_idle_session(
        self,
        model_id: str,
        predefined_task_name: Optional[str] = None
    ) -> Optional[Session]:
        """
        Find an IDLE session for reuse based on model_id and optional predefined_task_name.

        Matching logic:
        - If predefined_task_name provided: match BOTH predefined_task_name AND model_id
        - If no predefined_task_name: match model_id only

        This allows:
        - Multiple instances of same predefined task with different models (no conflict)
        - Session reuse for same predefined task + model combination

        Args:
            model_id: Model identifier (required)
            predefined_task_name: Optional predefined task name

        Returns:
            Session if found and reusable, None otherwise
        """
        async with self._lock:
            for session in self._sessions.values():
                # Skip if queue is full
                if session.is_queue_full:
                    continue

                # Skip if not ready (INITIALIZING or KILLED)
                if session.status not in [WorkerStatus.WAITING, WorkerStatus.WORKING]:
                    continue

                # Check model_id match (always required)
                if session.model_id != model_id:
                    continue

                # If predefined_task_name provided, must match
                if predefined_task_name is not None:
                    if session.predefined_task_name != predefined_task_name:
                        continue  # Task name doesn't match, skip this session

                    logger.info(
                        f"Found idle session {session.session_id} for predefined task "
                        f"'{predefined_task_name}' with model {model_id} (reuse)"
                    )
                    return session
                else:
                    # No predefined task requirement, just model_id match
                    logger.info(
                        f"Found idle session {session.session_id} for model {model_id} (reuse)"
                    )
                    return session

            return None

    async def enqueue_request(self, session_id: str, task: Task) -> Optional[asyncio.Event]:
        """
        Add request to session's FIFO queue and create task event.

        Args:
            session_id: Session identifier
            task: Task to enqueue

        Returns:
            Task event if enqueued successfully, None if queue is full
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for enqueue")
            return None

        if session.is_queue_full:
            logger.warning(f"Session {session_id} queue is full (max={settings.SESSION_QUEUE_MAX_SIZE})")
            return None

        try:
            # Create task event before enqueuing
            task_event = session.create_task_event(task.task_id)

            await session.request_queue.put(task)
            session.mark_activity()
            logger.info(f"Enqueued task {task.task_id} to session {session_id} (queue_size={session.queue_size})")
            return task_event
        except asyncio.QueueFull:
            logger.error(f"Session {session_id} queue unexpectedly full")
            return None

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
            session.mark_activity()
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

    async def update_session_status(self, session_id: str, status: WorkerStatus) -> Optional[Session]:
        """
        Update session status.

        If status is KILLED, automatically triggers session cleanup.

        Args:
            session_id: Session identifier
            status: New status

        Returns:
            Updated Session object, or None if session not found
        """
        session = await self.get_session(session_id)
        if session:
            old_status = session.status
            session.status = status
            logger.info(f"Session {session_id} status: {old_status.value} → {status.value}")

            # If status is KILLED, trigger cleanup
            if status == WorkerStatus.KILLED:
                await self.kill_session(session_id, reason="status_update")

        return session

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
            session.status = WorkerStatus.KILLED

            # Stop Docker container
            try:
                await docker_manager.stop_container(session.container_id)
                logger.info(f"Stopped container {session.container_id[:12]} for session {session_id}")
            except Exception as e:
                logger.error(f"Error stopping container for session {session_id}: {e}")

            # Release GPU
            await gpu_manager.release_gpu(session.gpu_device_id)

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


# Global session manager instance
session_manager = SessionManager()
