"""
GPU resource management - allocation, monitoring, and tracking.
"""

import asyncio
import logging
from typing import Dict, Optional, List

try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    logging.warning("pynvml not available - GPU monitoring disabled")

from app.core.config import settings
from app.models.gpu import GPUDevice

logger = logging.getLogger(__name__)


class GPUManager:
    """
    Singleton manager for GPU resources.
    Handles allocation, deallocation, and monitoring of GPU devices.
    """

    def __init__(self):
        self._devices: Dict[int, GPUDevice] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._refresh_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize GPU devices and start monitoring."""
        if self._initialized:
            return

        logger.info("Initializing GPU Manager...")

        if not PYNVML_AVAILABLE:
            logger.warning("NVIDIA ML library not available - creating mock GPU for testing")
            # Create mock GPU for development/testing
            self._devices[0] = GPUDevice(
                device_id=0,
                name="Mock GPU (pynvml not available)",
                memory_total_mb=8192,
                is_available=True
            )
            self._initialized = True
            return

        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            logger.info(f"Found {device_count} GPU device(s)")

            # Initialize only configured devices
            for device_id in settings.GPU_DEVICE_IDS:
                if device_id >= device_count:
                    logger.warning(f"GPU device {device_id} not found (only {device_count} devices available)")
                    continue

                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
                name = pynvml.nvmlDeviceGetName(handle)
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                self._devices[device_id] = GPUDevice(
                    device_id=device_id,
                    name=name if isinstance(name, str) else name.decode('utf-8'),
                    memory_total_mb=memory_info.total // (1024 * 1024),
                    is_available=True
                )
                logger.info(f"Initialized GPU {device_id}: {self._devices[device_id].name}")

            self._initialized = True

            # Start background metrics refresh
            self._refresh_task = asyncio.create_task(self._refresh_metrics_loop())
            logger.info("GPU Manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize GPU Manager: {e}")
            # Create mock device as fallback
            self._devices[0] = GPUDevice(
                device_id=0,
                name=f"Mock GPU (init failed: {str(e)[:50]})",
                memory_total_mb=8192,
                is_available=True
            )
            self._initialized = True

    async def shutdown(self):
        """Shutdown GPU Manager and cleanup resources."""
        logger.info("Shutting down GPU Manager...")

        # Cancel refresh task
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        # Shutdown NVML
        if PYNVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except Exception as e:
                logger.error(f"Error shutting down NVML: {e}")

        self._initialized = False
        logger.info("GPU Manager shutdown complete")

    async def allocate_gpu(self, task_difficulty: str, task_id: str) -> Optional[int]:
        """
        Allocate an available GPU for a task based on difficulty.

        Args:
            task_difficulty: Task difficulty level ("low" or "high")
            task_id: ID of the task requesting GPU

        Returns:
            GPU device ID if allocated, None if all matching GPUs are busy
        """
        async with self._lock:
            # Get GPU IDs matching the difficulty level
            matching_gpus = self.get_gpus_by_difficulty(task_difficulty)

            # Find first available GPU in matching set
            for device_id in matching_gpus:
                device = self._devices.get(device_id)
                if device and device.is_available:
                    device.is_available = False
                    device.current_job_id = task_id
                    logger.info(f"Allocated GPU {device_id} (difficulty={task_difficulty}) to task {task_id}")
                    return device_id

            logger.warning(f"No available GPU for task {task_id} with difficulty={task_difficulty}")
            return None

    def get_gpus_by_difficulty(self, difficulty: str) -> List[int]:
        """
        Get list of GPU device IDs matching difficulty level.

        Args:
            difficulty: Difficulty level ("low" or "high")

        Returns:
            List of device IDs matching the difficulty
        """
        from app.core.config import settings

        matching_gpus = []
        for device_id in self._devices.keys():
            gpu_difficulty = settings.GPU_DEVICE_DIFFICULTY.get(device_id, "low")
            if gpu_difficulty == difficulty:
                matching_gpus.append(device_id)

        return matching_gpus

    async def release_gpu(self, device_id: int, task_id: Optional[str] = None):
        """
        Release a GPU back to the pool.

        Args:
            device_id: GPU device ID to release
            task_id: Optional task ID for logging (not used for validation)
        """
        async with self._lock:
            if device_id in self._devices:
                job_id = self._devices[device_id].current_job_id
                self._devices[device_id].is_available = True
                self._devices[device_id].current_job_id = None
                log_msg = f"Released GPU {device_id} from job {job_id}"
                if task_id:
                    log_msg += f" (task {task_id})"
                logger.info(log_msg)
            else:
                logger.warning(f"Attempted to release unknown GPU {device_id}")

    async def get_gpu_status(self) -> List[GPUDevice]:
        """
        Get current status of all GPUs.

        Returns:
            List of GPU device status
        """
        return list(self._devices.values())

    async def _refresh_metrics_loop(self):
        """Background task to refresh GPU metrics."""
        logger.info(f"Starting GPU metrics refresh loop (interval: {settings.GPU_METRICS_REFRESH_INTERVAL}s)")

        while True:
            try:
                await asyncio.sleep(settings.GPU_METRICS_REFRESH_INTERVAL)
                await self._refresh_gpu_metrics()
            except asyncio.CancelledError:
                logger.info("GPU metrics refresh loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in GPU metrics refresh loop: {e}")

    async def _refresh_gpu_metrics(self):
        """Refresh GPU metrics (memory, temperature, utilization)."""
        if not PYNVML_AVAILABLE:
            return

        try:
            for device_id, device in self._devices.items():
                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)

                # Memory
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                device.memory_used_mb = memory_info.used // (1024 * 1024)

                # Utilization
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                device.utilization_percent = float(utilization.gpu)

                # Temperature
                try:
                    temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    device.temperature_celsius = float(temperature)
                except Exception:
                    # Temperature may not be available on all devices
                    pass

        except Exception as e:
            logger.error(f"Error refreshing GPU metrics: {e}")


# Global GPU manager instance
gpu_manager = GPUManager()
