"""
Configuration management for Web Server.
Loads environment variables using Pydantic Settings.
"""

from typing import List, Union
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str
    APP_VERSION: str
    LOG_LEVEL: str

    # CORS Configuration
    CORS_ORIGINS: Union[str, List[str]]

    # Proxmox API Configuration
    PROXMOX_API_URL: str
    PROXMOX_API_TOKEN: str  # Format: PVEAPIToken=root@pam!webserver=<token>
    PROXMOX_VERIFY_SSL: bool

    # Downstream Microservices (for future use)
    STEVENAI_SERVICE_URL: str  # Future stevenai-service
    FOOD101_SERVICE_URL: str   # Future food101-service
    LANDSINK_SERVICE_URL: str  # Future landsink-service

    # File Service Integration (existing service)
    FILE_SERVICE_URL: str
    FILE_SERVICE_API_KEY: str  # Frontend API key for file service

    @model_validator(mode="before")
    @classmethod
    def parse_cors_origins(cls, values):
        """Parse CORS_ORIGINS from comma-separated string to list."""
        if isinstance(values.get("CORS_ORIGINS"), str):
            values["CORS_ORIGINS"] = [
                origin.strip() for origin in values["CORS_ORIGINS"].split(",")
            ]
        return values

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
