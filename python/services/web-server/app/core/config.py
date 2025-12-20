"""
Configuration management for Web Server.
Loads environment variables using Pydantic Settings.
"""

import os
import yaml
from pathlib import Path
from typing import List, Union, Dict, Any
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

    # Host Server Configuration
    HOST_SERVER: str  # "us-west" or "us-east"

    # Proxmox Server Configuration
    PROXMOX_VERIFY_SSL: bool
    # US-West Proxmox Server
    PROXMOX_US_WEST_API_URL: str
    PROXMOX_US_WEST_API_TOKEN: str  # Format: PVEAPIToken=root@pam!webserver=<token>
    # US-East Proxmox Server (Backup)
    PROXMOX_US_EAST_API_URL: str
    PROXMOX_US_EAST_API_TOKEN: str

    # Downstream Microservices (for future use)
    STEVENAI_SERVICE_URL: str  # Future stevenai-service
    FOOD101_SERVICE_URL: str   # Future food101-service
    LANDSINK_SERVICE_URL: str  # Future landsink-service

    # File Service Integration
    FILE_SERVICE_URL: str
    FILE_SERVICE_API_KEY: str

    # GPU Service Integration
    GPU_SERVICE_URL: str
    GPU_SERVICE_API_KEY: str

    # Status Config (YAML file path)
    STATUS_CONFIG_PATH: str = "status-config.yaml"

    # Loaded status configuration from YAML
    _status_config: Dict[str, Any] = {}

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

    def load_status_config(self) -> Dict[str, Any]:
        """Load status configuration from YAML file."""
        if self._status_config:
            return self._status_config

        config_path = Path(self.STATUS_CONFIG_PATH)
        if not config_path.is_absolute():
            # If relative path, resolve from web-server directory
            base_dir = Path(__file__).parent.parent.parent
            config_path = base_dir / config_path

        if not config_path.exists():
            raise FileNotFoundError(f"Status config file not found: {config_path}")

        with open(config_path, 'r') as f:
            self._status_config = yaml.safe_load(f)

        return self._status_config

    def get_server_config(self, server_name: str) -> tuple[str, str]:
        """Get the Proxmox API URL and token for a given server name.

        Returns:
            tuple: (api_url, api_token)
        """
        config_map = {
            "us-west": (self.PROXMOX_US_WEST_API_URL, self.PROXMOX_US_WEST_API_TOKEN),
            "us-east": (self.PROXMOX_US_EAST_API_URL, self.PROXMOX_US_EAST_API_TOKEN),
        }
        return config_map.get(server_name, ("", ""))

    def get_service_config(self, service_name: str) -> tuple[str, str]:
        """Get the service URL and API key for a given service name.

        Returns:
            tuple: (service_url, api_key)
        """
        config_map = {
            "file-service": (self.FILE_SERVICE_URL, self.FILE_SERVICE_API_KEY),
            "gpu-service": (self.GPU_SERVICE_URL, self.GPU_SERVICE_API_KEY),
        }
        return config_map.get(service_name, ("", ""))


# Global settings instance
settings = Settings()
