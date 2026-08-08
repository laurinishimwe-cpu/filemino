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
    storage_backend: str = "local"
    file_retention_seconds: int = 86_400
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    r2_endpoint: str | None = None
    r2_signed_url_expiry_seconds: int = 900
    max_upload_size_bytes: int = 500 * 1024 * 1024
    guest_max_upload_size_bytes: int = 2 * 1024 * 1024 * 1024
    guest_max_duration_seconds: int = 3_600
    guest_max_resolution_height: int = 1080
    guest_max_jobs_per_hour: int = 10
    guest_max_concurrent_jobs: int = 2
    rate_limit_hash_salt: str = "development-only-change-me"
    free_max_duration_seconds: int = 600
    free_max_resolution_height: int = 1080
    job_ttl_seconds: int = 86_400

    ffmpeg_binary: str = "ffmpeg"
    ffmpeg_timeout_seconds: int = 3_600
    ffprobe_binary: str = "ffprobe"
    ffprobe_timeout_seconds: int = 30
    progress_persist_interval_seconds: float = 1.0
    redis_url: str = "redis://localhost:6379/0"
    rq_compression_queue_name: str = "compression"
    cpu_queue_name: str = "video-cpu"
    gpu_queue_name: str = "video-gpu"
    gpu_enabled: bool = False
    gpu_fallback_to_cpu: bool = True
    gpu_min_complexity: str = "heavy"
    gpu_available_encoders: str = "h264_nvenc"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
