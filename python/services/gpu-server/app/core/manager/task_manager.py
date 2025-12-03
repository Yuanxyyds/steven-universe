"""
Task manager singleton for tracking all running tasks.
"""

import asyncio
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Global task manager singleton.

    Responsibilities:
    - Hold references to GPU Manager, Session Manager, Docker Manager
    - Track all running tasks with their InstanceManagers
    - Provide unified interface for task lifecycle
    """

    def __init__(self):
        # Import singletons here to avoid circular imports
        from app.core.manager.gpu_manager import gpu_manager
        from app.core.manager.session_manager import session_manager
        from app.core.manager.docker_manager import docker_manager

        self.gpu_manager = gpu_manager
        self.session_manager = session_manager
        self.docker_manager = docker_manager

        self._running_tasks: Dict[str, 'InstanceManager'] = {}  # task_id -> instance
        self._lock = asyncio.Lock()

    async def register_task(self, task_id: str, instance_manager: 'InstanceManager'):
        """
        Register a running task.

        Args:
            task_id: Task identifier
            instance_manager: Instance manager handling this task
        """
        async with self._lock:
            self._running_tasks[task_id] = instance_manager
            logger.info(f"Registered task {task_id} ({len(self._running_tasks)} total running)")

    async def unregister_task(self, task_id: str):
        """
        Unregister a completed/failed task.

        Args:
            task_id: Task identifier
        """
        async with self._lock:
            self._running_tasks.pop(task_id, None)
            logger.info(f"Unregistered task {task_id} ({len(self._running_tasks)} remaining)")

    def get_running_tasks(self) -> List[str]:
        """
        Get list of running task IDs.

        Returns:
            List of task IDs currently being processed
        """
        return list(self._running_tasks.keys())

    async def shutdown_task(self, task_id: str):
        """
        Force shutdown a running task.

        Args:
            task_id: Task identifier to shutdown
        """
        instance = self._running_tasks.get(task_id)
        if instance:
            logger.warning(f"Force shutting down task {task_id}")
            await instance.shutdown()  # Instance manager handles cleanup
        else:
            logger.warning(f"Cannot shutdown task {task_id}: not found")


# Global task manager instance (singleton)
task_manager = TaskManager()
