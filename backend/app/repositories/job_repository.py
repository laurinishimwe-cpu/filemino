import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from redis import Redis

from app.models.image import ImageCompressionMode, ImageConversionOutputFormat, ImageOutputFormat, ImageResizeOption, JobTool
from app.models.job import Job, JobStatus, utc_now
from app.models.video import CompressionMode, ResolutionOption


class JobRepository(Protocol):
    def create(self, job: Job) -> Job: ...

    def get(self, job_id: UUID) -> Job | None: ...

    def save(self, job: Job) -> Job: ...

    def delete(self, job_id: UUID) -> None: ...


class InMemoryJobRepository:
    """Test and development repository with the same TTL semantics as Redis."""

    def __init__(self, ttl_seconds: int = 86_400, clock: Callable[[], datetime] = utc_now) -> None:
        self._jobs: dict[UUID, Job] = {}
        self._expires_at: dict[UUID, datetime] = {}
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def create(self, job: Job) -> Job:
        return self.save(job)

    def get(self, job_id: UUID) -> Job | None:
        expires_at = self._expires_at.get(job_id)
        if expires_at is not None and self._clock() >= expires_at:
            self.delete(job_id)
            return None
        return self._jobs.get(job_id)

    def save(self, job: Job) -> Job:
        self._jobs[job.id] = job
        self._expires_at[job.id] = self._clock() + timedelta(seconds=self._ttl_seconds)
        return job

    def delete(self, job_id: UUID) -> None:
        self._jobs.pop(job_id, None)
        self._expires_at.pop(job_id, None)


class RedisJobRepository:
    """Redis JSON records with a TTL; public APIs never expose these keys."""

    key_prefix = "fluxfile:jobs"

    def __init__(self, redis_client: Redis, ttl_seconds: int) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    def create(self, job: Job) -> Job:
        self._write(job)
        return job

    def get(self, job_id: UUID) -> Job | None:
        raw = self._redis.get(self._key(job_id))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            return _job_from_payload(payload)
        except (TypeError, ValueError, KeyError):
            self.delete(job_id)
            return None

    def save(self, job: Job) -> Job:
        self._write(job)
        return job

    def delete(self, job_id: UUID) -> None:
        self._redis.delete(self._key(job_id))

    def _write(self, job: Job) -> None:
        self._redis.set(self._key(job.id), json.dumps(_job_to_payload(job)), ex=self._ttl_seconds)

    def _key(self, job_id: UUID) -> str:
        return f"{self.key_prefix}:{job_id}"


def _job_to_payload(job: Job) -> dict[str, Any]:
    return {
        "id": str(job.id), "status": job.status.value, "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(), "original_filename": job.original_filename,
        "tool": job.tool.value,
        "client_hash": job.client_hash,
        "processing_queue": job.processing_queue,
        "input_storage_key": job.input_storage_key, "output_storage_key": job.output_storage_key,
        "compression_mode": job.compression_mode.value, "target_size_bytes": job.target_size_bytes,
        "resolution": job.resolution.value, "progress": job.progress, "stage": job.stage,
        "image_output_format": None if job.image_output_format is None else job.image_output_format.value,
        "image_resize": None if job.image_resize is None else job.image_resize.value,
        "image_quality_percent": job.image_quality_percent,
        "image_resize_percent": job.image_resize_percent,
        "image_custom_width": job.image_custom_width,
        "image_custom_height": job.image_custom_height,
        "image_lock_aspect_ratio": job.image_lock_aspect_ratio,
        "image_allow_resize_for_target": job.image_allow_resize_for_target,
        "image_conversion_output_format": None if job.image_conversion_output_format is None else job.image_conversion_output_format.value,
        "image_conversion_quality_percent": job.image_conversion_quality_percent,
        "image_conversion_background_color": job.image_conversion_background_color,
        "message": job.message, "input_metadata": job.input_metadata, "output_metadata": job.output_metadata,
        "target_failure_context": job.target_failure_context,
        "error_code": job.error_code, "safe_error_message": job.safe_error_message,
        "processing_started_at": _datetime_to_string(job.processing_started_at),
        "completed_at": _datetime_to_string(job.completed_at),
    }


def _job_from_payload(payload: dict[str, Any]) -> Job:
    tool = _job_tool(payload.get("tool", JobTool.VIDEO))
    return Job(
        id=UUID(payload["id"]), status=JobStatus(payload["status"]),
        created_at=datetime.fromisoformat(payload["created_at"]), updated_at=datetime.fromisoformat(payload["updated_at"]),
        original_filename=payload["original_filename"], input_storage_key=payload["input_storage_key"],
        tool=tool,
        client_hash=payload.get("client_hash"),
        processing_queue=payload.get("processing_queue", "video-cpu"),
        output_storage_key=payload.get("output_storage_key"),
        compression_mode=_compression_mode(payload["compression_mode"], tool),
        target_size_bytes=payload.get("target_size_bytes"), resolution=ResolutionOption(payload["resolution"]),
        image_output_format=_optional_image_output_format(payload.get("image_output_format")),
        image_resize=_optional_image_resize(payload.get("image_resize")),
        image_quality_percent=payload.get("image_quality_percent"),
        image_resize_percent=payload.get("image_resize_percent"),
        image_custom_width=payload.get("image_custom_width"),
        image_custom_height=payload.get("image_custom_height"),
        image_lock_aspect_ratio=payload.get("image_lock_aspect_ratio", True),
        image_allow_resize_for_target=payload.get("image_allow_resize_for_target", True),
        image_conversion_output_format=_optional_image_conversion_output_format(payload.get("image_conversion_output_format")),
        image_conversion_quality_percent=payload.get("image_conversion_quality_percent"),
        image_conversion_background_color=payload.get("image_conversion_background_color"),
        progress=payload["progress"], stage=payload["stage"], message=payload["message"],
        input_metadata=payload.get("input_metadata"), output_metadata=payload.get("output_metadata"),
        target_failure_context=payload.get("target_failure_context"),
        error_code=payload.get("error_code"), safe_error_message=payload.get("safe_error_message"),
        processing_started_at=_datetime_from_string(payload.get("processing_started_at")),
        completed_at=_datetime_from_string(payload.get("completed_at")),
    )


def _datetime_to_string(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _datetime_from_string(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def _compression_mode(value: str, tool: JobTool) -> CompressionMode | ImageCompressionMode:
    if tool is JobTool.IMAGE_COMPRESSION:
        return ImageCompressionMode(value)
    return CompressionMode(value)


def _optional_image_output_format(value: str | None) -> ImageOutputFormat | None:
    return None if value is None else ImageOutputFormat(value)


def _optional_image_resize(value: str | None) -> ImageResizeOption | None:
    return None if value is None else ImageResizeOption(value)


def _optional_image_conversion_output_format(value: str | None) -> ImageConversionOutputFormat | None:
    return None if value is None else ImageConversionOutputFormat(value)


def _job_tool(value: str | JobTool) -> JobTool:
    return JobTool({"video": JobTool.VIDEO_COMPRESSION, "image": JobTool.IMAGE_COMPRESSION}.get(value, value))
