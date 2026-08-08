from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.models.image import ImageCompressionMode, ImageConversionOutputFormat, ImageOutputFormat, ImageResizeOption, JobTool
from app.models.video import CompressionMode, ResolutionOption


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROBING = "probing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


VALID_JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.PROBING, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED},
    JobStatus.PROBING: {JobStatus.PROCESSING, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED},
    JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED},
    JobStatus.COMPLETED: {JobStatus.EXPIRED},
    JobStatus.FAILED: {JobStatus.EXPIRED},
    JobStatus.CANCELLED: {JobStatus.EXPIRED},
    JobStatus.EXPIRED: set(),
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_valid_transition(current: JobStatus, target: JobStatus) -> bool:
    return target in VALID_JOB_TRANSITIONS[current]


@dataclass(slots=True)
class Job:
    id: UUID = field(default_factory=uuid4)
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    original_filename: str = ""
    tool: JobTool = JobTool.VIDEO
    client_hash: str | None = None
    processing_queue: str = "video-cpu"
    input_storage_key: str = ""
    output_storage_key: str | None = None
    compression_mode: CompressionMode | ImageCompressionMode = CompressionMode.BALANCED
    target_size_bytes: int | None = None
    resolution: ResolutionOption = ResolutionOption.ORIGINAL
    image_output_format: ImageOutputFormat | None = None
    image_resize: ImageResizeOption | None = None
    image_quality_percent: int | None = None
    image_resize_percent: int | None = None
    image_custom_width: int | None = None
    image_custom_height: int | None = None
    image_lock_aspect_ratio: bool = True
    # Preserve the previous target-size behavior for persisted/legacy jobs.
    image_allow_resize_for_target: bool = True
    image_conversion_output_format: ImageConversionOutputFormat | None = None
    image_conversion_quality_percent: int | None = None
    image_conversion_background_color: str | None = None
    progress: int = 0
    stage: str = "queued"
    message: str = "Queued for processing"
    input_metadata: dict[str, Any] | None = None
    output_metadata: dict[str, Any] | None = None
    target_failure_context: dict[str, Any] | None = None
    error_code: str | None = None
    safe_error_message: str | None = None
    processing_started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.tool is JobTool.IMAGE_COMPRESSION and not isinstance(
            self.compression_mode, ImageCompressionMode
        ):
            raise ValueError("Image jobs require image compression modes.")
        if self.tool is JobTool.VIDEO_COMPRESSION and not isinstance(
            self.compression_mode, CompressionMode
        ):
            raise ValueError("Video jobs require video compression modes.")
        if self.tool is JobTool.IMAGE_CONVERSION and self.image_conversion_output_format is None:
            raise ValueError("Image conversion jobs require an output format.")
