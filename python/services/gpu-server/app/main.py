"""
GPU Service - Main FastAPI Application

Session-based GPU task execution service with SSE streaming.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.gpu_manager import gpu_manager
from app.core.session_manager import session_manager
from app.core.docker_manager import docker_manager
from app.core.model_config import model_config_manager
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
        # Initialize model config manager
        logger.info("Loading model presets configuration...")
        model_config_manager.load_config()
        logger.info(f"Loaded {len(model_config_manager._config.get('models', {}))} model configurations")

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

        logger.info(f"{settings.APP_NAME} started successfully")

        yield

    finally:
        # Cleanup on shutdown
        logger.info("Shutting down service...")

        # Cleanup session manager (kills all sessions)
        logger.info("Cleaning up sessions...")
        await session_manager.cleanup()

        # Cleanup Docker manager
        logger.info("Cleaning up Docker resources...")
        await docker_manager.cleanup()

        # Cleanup GPU manager
        logger.info("Cleaning up GPU manager...")
        await gpu_manager.cleanup()

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
