from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application configuration."""

    app_name: str = "FluxFile API"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    temp_directory: Path = Path(".tmp")
    max_upload_size_bytes: int = 500 * 1024 * 1024
    free_max_duration_seconds: int = 600
    free_max_resolution_height: int = 1080
    job_ttl_seconds: int = 86_400

    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
