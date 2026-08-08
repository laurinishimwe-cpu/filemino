import logging
from dataclasses import asdict
from uuid import UUID

from redis import Redis

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.encoders.image.conversion import PillowImageConverter
from app.models.job import JobStatus
from app.repositories.job_repository import RedisJobRepository
from app.services.image_conversion_service import ImageConversionService
from app.services.image_probe_service import ImageProbeService
from app.services.job_service import JobService
from app.services.rate_limit_service import RateLimitService
from app.storage.factory import create_storage

logger = logging.getLogger(__name__)


def run_image_conversion_job(job_id: str) -> None:
    """RQ entry point for static image conversion on the shared image CPU queue."""
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    repository = RedisJobRepository(redis_client, settings.job_ttl_seconds)
    job_service = JobService(
        repository,
        limiter=RateLimitService(redis_client, settings.rate_limit_hash_salt),
        max_jobs_per_hour=settings.guest_max_jobs_per_hour,
        max_concurrent_jobs=settings.guest_max_concurrent_jobs,
        job_ttl_seconds=settings.job_ttl_seconds,
        image_max_jobs_per_hour=settings.guest_image_max_jobs_per_hour,
        image_max_concurrent_jobs=settings.guest_image_max_concurrent_jobs,
        image_queue_name=settings.image_queue_name,
    )
    storage = create_storage(settings)
    probe = ImageProbeService(storage, min(settings.max_upload_size_bytes, settings.guest_image_max_upload_size_bytes), min(settings.image_max_pixels, settings.guest_image_max_pixels), settings.image_max_width, settings.image_max_height, settings.temp_directory)
    service = ImageConversionService(PillowImageConverter(settings.image_conversion_jpeg_quality, settings.image_conversion_webp_quality, settings.image_conversion_ico_sizes), storage, probe, settings.temp_directory)
    _process_image_conversion(UUID(job_id), job_service, service)


def _process_image_conversion(job_id: UUID, job_service: JobService, service: ImageConversionService) -> None:
    output_storage_key: str | None = None
    try:
        if job_service.get(job_id).status is JobStatus.CANCELLED:
            return
        logger.info("job_started", extra={"event": "job_started", "job_id": str(job_id), "tool": "image_conversion"})
        job_service.transition(job_id, JobStatus.PROBING, progress=20, stage="probing", message="Inspecting image")
        input_metadata = service.probe_input(job_service.get(job_id))
        job_service.set_input_metadata(job_id, asdict(input_metadata))
        if job_service.get(job_id).status is JobStatus.CANCELLED:
            return
        job_service.transition(job_id, JobStatus.PROCESSING, progress=60, stage="converting", message="Converting image")
        outcome = service.convert(job_service.get(job_id), input_metadata)
        output_storage_key = outcome.output_storage_key
        if job_service.get(job_id).status is JobStatus.CANCELLED:
            service.discard_output(output_storage_key)
            return
        job_service.set_output(job_id, output_storage_key, outcome.output_metadata)
        job_service.transition(job_id, JobStatus.COMPLETED, progress=100, stage="completed", message="Image ready")
    except ApplicationError as exc:
        if output_storage_key is not None:
            service.discard_output(output_storage_key)
        _mark_failed(job_service, job_id, exc.code)
    except Exception:
        if output_storage_key is not None:
            service.discard_output(output_storage_key)
        logger.exception("Image conversion worker failed for job %s", job_id)
        _mark_failed(job_service, job_id, "image_processing_failed")
        raise


def _mark_failed(job_service: JobService, job_id: UUID, error_code: str) -> None:
    try:
        job = job_service.get(job_id)
        if job.status not in {JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.EXPIRED}:
            job_service.transition(job_id, JobStatus.FAILED, stage="failed", message="Image processing failed", error_code=error_code, safe_error_message="Image conversion could not be completed.")
    except ApplicationError:
        logger.exception("Could not mark image conversion failed: %s", job_id)
