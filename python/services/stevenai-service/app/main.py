"""
StevenAI Service - Main FastAPI Application.
Chat service with RAG and model routing.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.dependencies import close_http_client
from app.services.rag_service import rag_service
from app.api import health, chat

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

    # Initialize RAG service (load models and indexes)
    logger.info("Initializing RAG service...")
    await rag_service.initialize()
    logger.info("✅ RAG service ready")

    yield

    # Shutdown
    logger.info("Shutting down StevenAI Service...")
    await close_http_client()
    logger.info("HTTP client closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="AI chat service with RAG for Steven's personal information",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health.router)
app.include_router(chat.router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "health": "GET /health",
            "chat_stream": "POST /chat/stream"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
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
