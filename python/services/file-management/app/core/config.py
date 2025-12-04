"""
Configuration management for File Management Service.
Loads environment variables and defines bucket access types.
"""

from enum import Enum
from typing import List
from pydantic_settings import BaseSettings


class BucketType(str, Enum):
    """Enum for bucket access types."""
    INTERNAL = "internal"
    SIGNED = "signed"
    PUBLIC = "public"
    UNKNOWN = "unknown"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # MinIO Configuration (internal network)
    MINIO_ENDPOINT: str           # Internal MinIO endpoint (e.g., 192.168.1.100:9000)
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False    # Set to True for HTTPS

    # Public Configuration (external access via Cloudflare Tunnel)
    PUBLIC_SERVICE_URL: str       # Public URL for this service (e.g., https://files.yourdomain.com)

    # Authentication
    INTERNAL_SECRET_KEY: str  # For backend services
    FRONTEND_API_KEY: str     # For frontend applications

    # Signed URL Configuration
    DEFAULT_SIGNED_URL_EXPIRATION: int = 3600  # 1 hour in seconds
    MAX_SIGNED_URL_EXPIRATION: int = 86400     # 24 hours max

    # Application
    LOG_LEVEL: str = "INFO"

    # Streaming Upload Configuration
    MAX_BUFFERED_CHUNKS: int = 50  # Number of 256KB chunks to buffer (default: 10 = 2.5MB)
                                   # Increase for high-speed networks (e.g., 50 = 12.5MB for 1Gbps+)

    # Bucket Type Definitions
    # Type 1: Private + Internal Only (backend services only)
    INTERNAL_BUCKETS: List[str] = ["models"]

    # Type 2: Private + Signed URLs (frontend can request time-limited access)
    SIGNED_BUCKETS: List[str] = ["user-uploads", "model-outputs"]

    # Type 3: Public buckets (direct URL access, always open)
    PUBLIC_BUCKETS: List[str] = ["public"]

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_bucket_type(bucket: str) -> BucketType:
    """
    Determine the access type for a given bucket.

    Args:
        bucket: Bucket name

    Returns:
        BucketType enum value
    """
    if bucket in settings.INTERNAL_BUCKETS:
        return BucketType.INTERNAL
    elif bucket in settings.SIGNED_BUCKETS:
        return BucketType.SIGNED
    elif bucket in settings.PUBLIC_BUCKETS:
        return BucketType.PUBLIC
    else:
        return BucketType.UNKNOWN


def validate_bucket(bucket: str) -> bool:
    """Check if bucket is configured in any category."""
    all_buckets = (
        settings.INTERNAL_BUCKETS +
        settings.SIGNED_BUCKETS +
        settings.PUBLIC_BUCKETS
    )
    return bucket in all_buckets
