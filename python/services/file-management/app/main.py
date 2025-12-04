"""
File Management Service - Main Application
FastAPI app with three-tier bucket architecture for MinIO/S3 operations.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared_schemas.file_service import HealthCheckResponse
from app.core.config import settings
from app.s3.client import s3_client
from app.api import internal, signed, public

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info("Starting File Management Service...")

    # Initialize buckets with proper policies
    try:
        logger.info("Initializing buckets...")

        # Type 1: Internal buckets (private policy)
        for bucket in settings.INTERNAL_BUCKETS:
            s3_client.ensure_bucket_exists(bucket)
            logger.info(f" Internal bucket ready: {bucket}")

        # Type 2: Signed URL buckets (private policy)
        for bucket in settings.SIGNED_BUCKETS:
            s3_client.ensure_bucket_exists(bucket)
            logger.info(f" Signed URL bucket ready: {bucket}")

        # Type 3: Public buckets (public-read policy)
        for bucket in settings.PUBLIC_BUCKETS:
            s3_client.ensure_bucket_exists(bucket)
            logger.info(f" Public bucket ready: {bucket}")

        logger.info("All buckets initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize buckets: {e}")
        # Continue anyway - buckets can be created on-demand

    logger.info("File Management Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down File Management Service...")


# Create FastAPI app
app = FastAPI(
    title="File Management Service",
    description="Three-tier file management with MinIO/S3: Internal, Signed URL, and Public buckets",
    version="1.0.0",
    lifespan=lifespan
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Public bucket accessible from anywhere
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(internal.router)

# Signed router has two parts (auth and no-auth)
for router in signed.routers:
    app.include_router(router)

# Public router has two parts (auth and no-auth)
for router in public.routers:
    app.include_router(router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": "File Management Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "internal": "/internal/* (Type 1: Private + Internal only)",
            "signed": "/signed/* (Type 2: Private + Signed URLs)",
            "public": "/public/* (Type 3: Public buckets)",
            "health": "/health"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/health", tags=["health"], response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Test S3 connection
        s3_client.client.list_buckets()

        return HealthCheckResponse(
            status="healthy",
            s3_connection="ok"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "s3_connection": "failed"
            }
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "detail": "Internal server error"
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
        timeout_keep_alive=7200,  # 2 hours for very large file uploads
        limit_max_requests=0,     # No limit on requests
        limit_concurrency=100     # Allow more concurrent connections
    )
