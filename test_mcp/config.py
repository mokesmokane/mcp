"""
Configuration settings for the MCP server.
"""
import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings."""
    # Server settings
    APP_NAME: str = "Test MCP Server"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # CORS settings
    CORS_ORIGINS: List[str] = ["*"]

    # API settings
    API_V1_STR: str = "/api/v1"

    # Model settings
    MODEL_NAME: str = "test-model"

    # Supabase settings
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # OpenAI settings
    OPENAI_API_KEY: str = ""
    OPENAI_VECTOR_STORE_ID: str = ""

    # Load from .env file if it exists
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Create settings instance
settings = Settings()
