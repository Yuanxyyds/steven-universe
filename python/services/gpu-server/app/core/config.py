"""
Configuration management for GPU Service.
Loads environment variables using Pydantic Settings.
"""

from typing import List, Dict, Union
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str
    APP_VERSION: str
    LOG_LEVEL: str

    # CORS Configuration (will be parsed by model_validator)
    CORS_ORIGINS: Union[str, List[str]]

    # GPU Configuration (will be parsed by model_validator)
    GPU_DEVICE_IDS: Union[str, List[int]]
    GPU_DEVICE_DIFFICULTY: Union[str, Dict[int, str]]  # Map device_id to difficulty ("low"/"high")
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
    ALLOWED_DOCKER_IMAGES: Union[str, List[str]]

    # Model Cache Configuration
    MODEL_CACHE_DIR: str
    AUTO_FETCH_MODELS: bool

    # File Service Integration
    FILE_SERVICE_URL: str
    FILE_SERVICE_INTERNAL_KEY: str

    # Authentication
    INTERNAL_API_KEY: str

    @model_validator(mode="before")
    @classmethod
    def parse_env_values(cls, values):
        """Parse environment variables from strings to proper types."""

        # Parse CORS_ORIGINS from comma-separated string to list
        if isinstance(values.get("CORS_ORIGINS"), str):
            values["CORS_ORIGINS"] = [
                origin.strip() for origin in values["CORS_ORIGINS"].split(",")
            ]

        # Parse GPU_DEVICE_IDS from comma-separated string to list of ints
        if isinstance(values.get("GPU_DEVICE_IDS"), str):
            values["GPU_DEVICE_IDS"] = [
                int(device_id.strip()) for device_id in values["GPU_DEVICE_IDS"].split(",")
            ]

        # Parse ALLOWED_DOCKER_IMAGES from comma-separated string to list
        if isinstance(values.get("ALLOWED_DOCKER_IMAGES"), str):
            values["ALLOWED_DOCKER_IMAGES"] = [
                image.strip() for image in values["ALLOWED_DOCKER_IMAGES"].split(",")
            ]

        # Parse GPU_DEVICE_DIFFICULTY from comma-separated string to dict
        # Format: "0:low,1:high"
        if isinstance(values.get("GPU_DEVICE_DIFFICULTY"), str):
            result = {}
            for pair in values["GPU_DEVICE_DIFFICULTY"].split(","):
                device_id, difficulty = pair.split(":")
                result[int(device_id.strip())] = difficulty.strip()
            values["GPU_DEVICE_DIFFICULTY"] = result

        return values

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_parse_none_str=None,
    )


# Global settings instance
settings = Settings()
