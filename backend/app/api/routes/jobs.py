from datetime import timedelta
from pathlib import Path
import shutil
import tempfile
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api.dependencies import get_job_service, get_storage
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.models.job import JobStatus, utc_now
from app.models.image import JobTool
from app.schemas.job import DownloadResponse, JobResponse
from app.services.job_service import JobService
from app.storage.base import FileStorage

router = APIRouter()


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, service: Annotated[JobService, Depends(get_job_service)]) -> JobResponse:
    return JobResponse.model_validate(service.get(job_id))


@router.delete("/{job_id}", response_model=JobResponse, status_code=status.HTTP_200_OK)
def cancel_job(job_id: UUID, service: Annotated[JobService, Depends(get_job_service)]) -> JobResponse:
    return JobResponse.model_validate(service.cancel(job_id))


@router.get("/{job_id}/download", response_model=DownloadResponse)
def get_download_url(job_id: UUID, service: Annotated[JobService, Depends(get_job_service)], storage: Annotated[FileStorage, Depends(get_storage)]) -> DownloadResponse:
    job = service.get(job_id)
    if job.status is not JobStatus.COMPLETED or not job.output_storage_key:
        raise ValidationError("The output is not ready for download.")
    settings = get_settings(); expires_at = utc_now() + timedelta(seconds=settings.r2_signed_url_expiry_seconds)
    if settings.storage_backend == "local":
        return DownloadResponse(download_url=f"{settings.api_prefix}/jobs/{job_id}/download/content", expires_at=expires_at)
    signed = storage.create_download_url(job.output_storage_key, expires_at)
    return DownloadResponse(download_url=signed.url, expires_at=signed.expires_at)


@router.get("/{job_id}/download/content")
def download_local_content(job_id: UUID, service: Annotated[JobService, Depends(get_job_service)], storage: Annotated[FileStorage, Depends(get_storage)]):
    settings = get_settings()
    if settings.storage_backend != "local":
        raise ValidationError("Direct content download is only available for local development.")
    job = service.get(job_id)
    if job.status is not JobStatus.COMPLETED or not job.output_storage_key:
        raise ValidationError("The output is not ready for download.")
    workspace = tempfile.mkdtemp(dir=settings.temp_directory)
    suffix, filename, media_type = _download_details(job.tool, job.output_metadata)
    output_path = storage.download_to(job.output_storage_key, Path(workspace) / f"download{suffix}")
    return FileResponse(output_path, filename=filename, media_type=media_type, background=BackgroundTask(shutil.rmtree, workspace, True))


def _download_details(tool: JobTool, metadata: dict | None) -> tuple[str, str, str]:
    if tool is not JobTool.IMAGE:
        return ".mp4", "compressed-video.mp4", "video/mp4"
    image_format = (metadata or {}).get("format")
    details = {
        "JPEG": (".jpg", "compressed-image.jpg", "image/jpeg"),
        "PNG": (".png", "compressed-image.png", "image/png"),
        "WEBP": (".webp", "compressed-image.webp", "image/webp"),
    }
    return details.get(image_format, (".image", "compressed-image", "application/octet-stream"))
