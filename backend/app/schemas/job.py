from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus
from app.models.image import ImageCompressionMode, ImageConversionOutputFormat, ImageOutputFormat, ImageResizeOption, JobTool
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
    tool: JobTool = JobTool.VIDEO
    compression_mode: CompressionMode | ImageCompressionMode
    target_size_bytes: int | None = None
    resolution: ResolutionOption
    image_output_format: ImageOutputFormat | None = None
    image_resize: ImageResizeOption | None = None
    image_quality_percent: int | None = Field(default=None, ge=1, le=100)
    image_resize_percent: int | None = Field(default=None, ge=1, le=100)
    image_custom_width: int | None = Field(default=None, ge=1)
    image_custom_height: int | None = Field(default=None, ge=1)
    image_lock_aspect_ratio: bool = True
    image_allow_resize_for_target: bool = True
    image_conversion_output_format: ImageConversionOutputFormat | None = None
    image_conversion_quality_percent: int | None = Field(default=None, ge=1, le=100)
    image_conversion_background_color: str | None = None
    image_conversion_ico_sizes: tuple[int, ...] | None = None
    image_conversion_ico_source_size: int | None = None
    progress: int = Field(ge=0, le=100)
    stage: str
    message: str
    input_metadata: dict[str, Any] | None = None
    output_metadata: dict[str, Any] | None = None
    target_failure_context: dict[str, Any] | None = None
    error_code: str | None = None
    safe_error_message: str | None = None
    processing_started_at: datetime | None = None
    completed_at: datetime | None = None


class DownloadResponse(BaseModel):
    download_url: str
    expires_at: datetime
