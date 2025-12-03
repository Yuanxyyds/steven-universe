"""
GPU Service - Main FastAPI Application

Session-based GPU task execution service with SSE streaming.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.manager.gpu_manager import gpu_manager
from app.core.manager.session_manager import session_manager
from app.core.manager.docker_manager import docker_manager
from app.core.manager.model_downloader import model_downloader
from app.core.manager.task_manager import task_manager
from app.api import health, tasks, sessions

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles initialization and cleanup of all managers.
    """
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    try:
        # Initialize model downloader
        logger.info("Initializing model downloader...")
        await model_downloader.initialize()
        logger.info(f"Model downloader initialized with {len(model_downloader.get_cached_models())} cached models")

        # Initialize GPU manager
        logger.info("Initializing GPU manager...")
        await gpu_manager.initialize()
        gpu_devices = await gpu_manager.get_gpu_status()
        logger.info(f"Initialized {len(gpu_devices)} GPU device(s)")

        for device in gpu_devices:
            difficulty = settings.GPU_DEVICE_DIFFICULTY.get(device.device_id, "unknown")
            logger.info(
                f"  GPU {device.device_id}: {device.name} "
                f"(difficulty={difficulty}, memory={device.memory_total_mb}MB)"
            )

        # Initialize Docker manager
        logger.info("Initializing Docker manager...")
        await docker_manager.initialize()
        logger.info("Docker manager initialized")

        # Initialize session manager (starts background monitoring)
        logger.info("Initializing session manager...")
        await session_manager.initialize()
        logger.info("Session manager initialized")

        # TaskManager is automatically initialized (holds references to singletons)
        logger.info(f"TaskManager ready (tracking {len(task_manager.get_running_tasks())} running tasks)")

        logger.info(f"{settings.APP_NAME} started successfully")

        yield

    finally:
        # Cleanup on shutdown
        logger.info("Shutting down service...")

        # Shutdown all running tasks
        running_tasks = task_manager.get_running_tasks()
        if running_tasks:
            logger.info(f"Shutting down {len(running_tasks)} running tasks...")
            for task_id in running_tasks:
                await task_manager.shutdown_task(task_id)

        # Shutdown session manager (kills all sessions)
        logger.info("Shutting down sessions...")
        await session_manager.shutdown()

        logger.info(f"{settings.APP_NAME} shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Session-based GPU task execution service with SSE streaming",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(tasks.router, prefix="/api", tags=["Tasks"])
app.include_router(sessions.router, prefix="/api", tags=["Sessions"])


@app.get("/")
async def root():
    """
    Root endpoint with service information.
    """
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
