"""
Application Configuration
Uses pydantic-settings for environment variable management
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Construction AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./construction_ai.db"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # File Upload
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB
    ALLOWED_EXTENSIONS: list[str] = [".dwg", ".dxf", ".pdf", ".png", ".jpg", ".jpeg"]

    # LLM APIs
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # YOLO Models
    YOLO_MODEL_PATH: str = "./ml/yolo/models/best.pt"
    YOLO_BOUNDARY_MODEL_PATH: str = "../datascience/runs/yolo12xtrain_floorplan_boundary/yolo12x_floorplan_boundary_exp2/weights/best.pt"
    YOLO_OBJECT_MODEL_PATH: str = "../datascience/runs/yolo12xtrain/yolo12x_exp3/weights/best.pt"
    
    # PDF Processing
    PDF_DPI: int = 300
    POPPLER_PATH: Optional[str] = None  # Set if poppler not in PATH
    
    DEFAULT_STUD_SPACING_INCHES: int = 16  # 16" O.C.
    STANDARD_LUMBER_LENGTHS: list[int] = [96, 120, 144, 168, 192, 240]  # inches (8', 10', 12', 14', 16', 20')

    # Optimization
    CUT_OPTIMIZATION_KERF: float = 0.125  # inches (saw blade width)

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
