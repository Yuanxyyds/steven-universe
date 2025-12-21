"""
Configuration management for StevenAI Service.
Loads environment variables using Pydantic Settings.
"""

from typing import List, Union
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "StevenAI Service"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    # CORS Configuration
    CORS_ORIGINS: Union[str, List[str]]

    # OpenAI Configuration
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # GPU Service Configuration
    GPU_SERVICE_URL: str
    GPU_SERVICE_API_KEY: str
    GPU_SERVICE_HEALTH_CHECK_TIMEOUT: int = 5  # seconds
    GPU_MODELS: Union[str, List[str]] = ""  # Comma-separated list of accepted GPU model IDs

    # RAG Configuration
    RAG_TOP_K: int = 3
    RAG_EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    RAG_DOCUMENT_PATH: str = "app/data/rag_document.json"
    RAG_QA_PATH: str = "app/data/rag_qa.json"
    RAG_INDEX_PATH: str = "app/data/faiss_indexes"

    # Streaming Configuration
    STREAM_BUFFER_SIZE: int = 5  # Buffer 5+ chars before sending
    STREAM_FLUSH_TIMEOUT: float = 0.5  # Flush buffer after 0.5s

    # Authentication
    INTERNAL_API_KEY: str

    @model_validator(mode="before")
    @classmethod
    def parse_lists(cls, values):
        """Parse comma-separated strings to lists."""
        # Parse CORS_ORIGINS
        if isinstance(values.get("CORS_ORIGINS"), str):
            values["CORS_ORIGINS"] = [
                origin.strip() for origin in values["CORS_ORIGINS"].split(",")
            ]

        # Parse GPU_MODELS
        if isinstance(values.get("GPU_MODELS"), str):
            gpu_models_str = values["GPU_MODELS"].strip()
            if gpu_models_str:
                values["GPU_MODELS"] = [
                    model.strip() for model in gpu_models_str.split(",")
                ]
            else:
                values["GPU_MODELS"] = []

        return values

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
