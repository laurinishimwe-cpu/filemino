from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.dependencies import get_job_service, get_rate_limiter
from app.core.config import Settings, get_settings
from app.schemas.job import JobResponse, VideoJobCreateRequest
from app.schemas.video import VideoMetadataResponse
from app.services.job_service import JobService
from app.services.rate_limit_service import RateLimitService
from app.services.video_probe_service import VideoProbeService
from app.storage.local import LocalStorage
from app.storage.factory import create_storage

router = APIRouter()


def get_video_probe_service(settings: Annotated[Settings, Depends(get_settings)]) -> VideoProbeService:
    return VideoProbeService(
        storage=create_storage(settings),
        ffprobe_binary=settings.ffprobe_binary,
        max_upload_size_bytes=settings.max_upload_size_bytes,
        timeout_seconds=settings.ffprobe_timeout_seconds,
        scratch_directory=settings.temp_directory,
    )


@router.post("/probe", response_model=VideoMetadataResponse)
def probe_video(
    file: Annotated[UploadFile, File(description="Video file to inspect")],
    service: Annotated[VideoProbeService, Depends(get_video_probe_service)],
) -> VideoMetadataResponse:
    metadata = service.probe_upload(file.file, file.filename)
    return VideoMetadataResponse.model_validate(metadata)


@router.post("/jobs", response_model=JobResponse, status_code=202, deprecated=True, include_in_schema=False)
def create_video_job(
    request: VideoJobCreateRequest,
    http_request: Request,
    service: Annotated[JobService, Depends(get_job_service)],
    limiter: Annotated[RateLimitService, Depends(get_rate_limiter)],
) -> JobResponse:
    """Development-only legacy endpoint; production clients must complete an upload first."""
    job = service.create_video_job(
        original_filename=request.original_filename,
        compression_mode=request.compression_mode,
        target_size_bytes=request.target_size_bytes,
        resolution=request.resolution,
        input_metadata=request.input_metadata,
        client_hash=limiter.subject_hash(http_request.client.host if http_request.client else "unknown"),
    )
    return JobResponse.model_validate(job)
