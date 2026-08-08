from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_job_service, get_rate_limiter, get_upload_service
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.schemas.job import JobResponse
from app.schemas.upload import UploadInitializeRequest, UploadInitializeResponse
from app.services.job_service import JobService
from app.services.upload_service import UploadService
from app.services.rate_limit_service import RateLimitService

router = APIRouter()


@router.post("", response_model=UploadInitializeResponse, status_code=status.HTTP_201_CREATED)
def initialize_upload(request: UploadInitializeRequest, http_request: Request, service: Annotated[UploadService, Depends(get_upload_service)], limiter: Annotated[RateLimitService, Depends(get_rate_limiter)]) -> UploadInitializeResponse:
    client_hash=limiter.subject_hash(http_request.client.host if http_request.client else "unknown")
    upload, signed = service.initialize(request.filename, request.content_type,client_hash)
    return UploadInitializeResponse(upload_id=upload.id, storage_key=upload.storage_key, upload_url=signed.url, expires_at=signed.expires_at)


@router.post("/{upload_id}/complete", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def complete_upload(upload_id: UUID, upload_service: Annotated[UploadService, Depends(get_upload_service)], job_service: Annotated[JobService, Depends(get_job_service)]) -> JobResponse:
    return JobResponse.model_validate(upload_service.complete_video_upload(upload_id, job_service))


@router.put("/{upload_id}/content", status_code=status.HTTP_204_NO_CONTENT)
async def upload_local_content(upload_id: UUID, request: Request, service: Annotated[UploadService, Depends(get_upload_service)]) -> None:
    if get_settings().storage_backend != "local":
        raise ValidationError("Direct upload content is only available for local development.")
    body = await request.body()
    service.store_local_content(upload_id, BytesIO(body))
