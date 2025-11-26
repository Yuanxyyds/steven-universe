"""
Configuration management for GPU Service.
Loads environment variables using Pydantic Settings.
"""

from typing import List, Dict
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str
    APP_VERSION: str
    LOG_LEVEL: str

    # CORS Configuration
    CORS_ORIGINS: List[str]

    # GPU Configuration
    GPU_DEVICE_IDS: List[int]
    GPU_DEVICE_DIFFICULTY: Dict[int, str]  # Map device_id to difficulty ("low"/"high")
    GPU_METRICS_REFRESH_INTERVAL: int = 5

    # Session Configuration
    SESSION_IDLE_TIMEOUT_SECONDS: int = 300  # 5 minutes
    SESSION_MAX_LIFETIME_SECONDS: int = 3600  # 1 hour
    SESSION_QUEUE_MAX_SIZE: int = 5
    SESSION_MONITOR_INTERVAL: int = 30

    # Task Configuration
    DEFAULT_TASK_TIMEOUT: int = 300  # 5 minutes
    MAX_TASK_TIMEOUT: int = 1800  # 30 minutes
    TASK_MEMORY_LIMIT: str = "16g"
    TASK_CPU_QUOTA: int = 100000

    # Legacy Job Configuration (for backward compatibility)
    DEFAULT_JOB_TIMEOUT: int = 3600
    MAX_JOB_TIMEOUT: int = 86400
    MAX_QUEUE_SIZE: int = 10
    JOB_MEMORY_LIMIT: str = "16g"
    JOB_CPU_QUOTA: int = 100000

    # Docker Configuration
    DOCKER_SOCKET_PATH: str
    ALLOWED_DOCKER_IMAGES: List[str]

    # Model Cache Configuration
    MODEL_CACHE_DIR: str
    AUTO_FETCH_MODELS: bool

    # File Service Integration
    FILE_SERVICE_URL: str
    FILE_SERVICE_INTERNAL_KEY: str

    # Authentication
    INTERNAL_API_KEY: str

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string to list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("GPU_DEVICE_IDS", mode="before")
    @classmethod
    def parse_gpu_device_ids(cls, v):
        """Parse GPU_DEVICE_IDS from comma-separated string to list of ints."""
        if isinstance(v, str):
            return [int(device_id.strip()) for device_id in v.split(",")]
        return v

    @field_validator("ALLOWED_DOCKER_IMAGES", mode="before")
    @classmethod
    def parse_allowed_images(cls, v):
        """Parse ALLOWED_DOCKER_IMAGES from comma-separated string to list."""
        if isinstance(v, str):
            return [image.strip() for image in v.split(",")]
        return v

    @field_validator("GPU_DEVICE_DIFFICULTY", mode="before")
    @classmethod
    def parse_gpu_difficulty(cls, v):
        """
        Parse GPU_DEVICE_DIFFICULTY from comma-separated string to dict.
        Format: "0:low,1:high"
        """
        if isinstance(v, str):
            result = {}
            for pair in v.split(","):
                device_id, difficulty = pair.split(":")
                result[int(device_id.strip())] = difficulty.strip()
            return result
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
