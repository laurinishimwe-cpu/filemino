from typing import Annotated
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import get_image_probe_service, get_image_upload_service, get_job_service
from app.schemas.image import ImageConversionJobCreateRequest, ImageJobCreateRequest, ImageMetadataResponse
from app.schemas.job import JobResponse
from app.services.image_probe_service import ImageProbeService
from app.services.job_service import JobService
from app.services.upload_service import UploadService

router = APIRouter()


@router.post("/probe", response_model=ImageMetadataResponse)
def probe_image(file: Annotated[UploadFile, File(description="Image file to inspect")], service: Annotated[ImageProbeService, Depends(get_image_probe_service)]) -> ImageMetadataResponse:
    return ImageMetadataResponse.model_validate(service.probe_upload(file.file, file.filename))


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_image_job(request: ImageJobCreateRequest, upload_service: Annotated[UploadService, Depends(get_image_upload_service)], job_service: Annotated[JobService, Depends(get_job_service)]) -> JobResponse:
    return JobResponse.model_validate(upload_service.complete_image_upload(
        request.upload_id,
        job_service,
        request.compression_mode,
        request.target_size_bytes,
        request.output_format,
        request.resize,
        request.quality_percent,
        request.resize_percent,
        request.custom_width,
        request.custom_height,
        request.lock_aspect_ratio,
        request.allow_resize_for_target,
    ))


@router.post("/conversion-jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_image_conversion_job(request: ImageConversionJobCreateRequest, upload_service: Annotated[UploadService, Depends(get_image_upload_service)], job_service: Annotated[JobService, Depends(get_job_service)]) -> JobResponse:
    return JobResponse.model_validate(upload_service.complete_image_conversion_upload(request.upload_id, job_service, request.output_format, request.quality_percent, request.background_color))
