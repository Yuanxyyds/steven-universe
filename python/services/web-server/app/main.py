"""
Web Server - Main FastAPI Application
API Gateway that routes requests to specialized microservices.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.dependencies import close_http_client
from app.api import health, stats, landsink, food, chat

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
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("HTTP client will be initialized on first request")

    yield

    # Shutdown
    logger.info("Shutting down Web Server...")
    await close_http_client()
    logger.info("HTTP client closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="API Gateway for steven-universe microservices",
    version=settings.APP_VERSION,
    lifespan=lifespan
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(health.router)
app.include_router(stats.router)
app.include_router(landsink.router)
app.include_router(food.router)
app.include_router(chat.router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "health": {
                "GET /health": "Service health check",
                "GET /health/services": "Downstream services status"
            },
            "stats": {
                "GET /stats/servers": "Proxmox server statistics"
            },
            "predictions": {
                "GET /predictions/landsink?year=YYYY": "Climate prediction (Phase 4)"
            },
            "classifications": {
                "POST /classifications/food": "Food image classification (Phase 3)"
            },
            "chat": {
                "GET /chat/query?q=...&model=...&context=...": "AI chatbot query (Phase 2)"
            }
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }


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
        log_level=settings.LOG_LEVEL.lower()
    )
