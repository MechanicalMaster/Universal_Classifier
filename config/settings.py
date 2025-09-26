"""Configuration settings for the PDF/Image processing service."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    openai_api_key: str = Field(..., description="OpenAI API key for Vision API")
    
    # File Processing Limits
    max_file_size_mb: int = Field(default=100, description="Maximum file size in MB")
    max_total_pages: int = Field(default=200, description="Maximum total pages per request")
    max_pages_per_document: int = Field(default=50, description="Maximum pages per document")
    
    # Processing Configuration
    upload_dir: str = Field(default="/tmp/uploads", description="Directory for temporary file uploads")
    log_level: str = Field(default="INFO", description="Logging level")
    rate_limit_per_minute: int = Field(default=30, description="API rate limit per minute (conservative)")
    
    # Vision API Configuration
    vision_model: str = Field(default="gpt-4o", description="Latest GPT-4o vision model")
    max_retries: int = Field(default=3, description="Maximum retries for API calls")
    retry_delay: float = Field(default=1.0, description="Initial retry delay in seconds")
    
    # Performance Settings
    concurrent_requests: int = Field(default=5, description="Maximum concurrent requests")
    request_timeout: int = Field(default=600, description="Request timeout in seconds (10 minutes)")
    memory_limit_gb: int = Field(default=2, description="Memory limit per processing job in GB")
    
    # Image Processing
    image_dpi: int = Field(default=300, description="DPI for PDF to image conversion")
    max_image_size_mb: int = Field(default=4, description="Maximum image size for Vision API")
    
    # Environment
    environment: str = Field(default="development", description="Environment (development/production)")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
