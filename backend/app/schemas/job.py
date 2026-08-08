from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus
from app.models.video import CompressionMode, ResolutionOption


class VideoJobCreateRequest(BaseModel):
    original_filename: str = Field(min_length=1, max_length=255)
    compression_mode: CompressionMode = CompressionMode.BALANCED
    target_size_bytes: int | None = Field(default=None, gt=0)
    resolution: ResolutionOption = ResolutionOption.ORIGINAL
    input_metadata: dict[str, Any] | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    original_filename: str
    compression_mode: CompressionMode
    target_size_bytes: int | None = None
    resolution: ResolutionOption
    progress: int = Field(ge=0, le=100)
    stage: str
    message: str
    input_metadata: dict[str, Any] | None = None
    output_metadata: dict[str, Any] | None = None
    error_code: str | None = None
    safe_error_message: str | None = None
    processing_started_at: datetime | None = None
    completed_at: datetime | None = None


class DownloadResponse(BaseModel):
    download_url: str
    expires_at: datetime
