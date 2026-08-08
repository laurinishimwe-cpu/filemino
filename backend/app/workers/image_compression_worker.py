import logging
from dataclasses import asdict
from uuid import UUID

from redis import Redis

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.encoders.image.base import ImageEncoderConfig, ImageEncodingError, ImageTargetSizeUnreachable
from app.encoders.image.pillow_encoder import PillowImageEncoder
from app.models.job import JobStatus
from app.repositories.job_repository import RedisJobRepository
from app.services.image_compression_service import ImageCompressionService
from app.services.image_probe_service import ImageProbeService
from app.services.job_service import JobService
from app.services.rate_limit_service import RateLimitService
from app.storage.factory import create_storage

logger = logging.getLogger(__name__)


def run_image_compression_job(job_id: str) -> None:
    """RQ entry point for CPU image compression; encoder details remain isolated."""
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    repository = RedisJobRepository(redis_client, settings.job_ttl_seconds)
    job_service = JobService(repository, limiter=RateLimitService(redis_client, settings.rate_limit_hash_salt), max_jobs_per_hour=settings.guest_max_jobs_per_hour, max_concurrent_jobs=settings.guest_max_concurrent_jobs, job_ttl_seconds=settings.job_ttl_seconds, image_max_jobs_per_hour=settings.guest_image_max_jobs_per_hour, image_max_concurrent_jobs=settings.guest_image_max_concurrent_jobs, image_queue_name=settings.image_queue_name)
    storage = create_storage(settings)
    probe = ImageProbeService(storage, min(settings.max_upload_size_bytes, settings.guest_image_max_upload_size_bytes), min(settings.image_max_pixels, settings.guest_image_max_pixels), settings.image_max_width, settings.image_max_height, settings.temp_directory)
    service = ImageCompressionService(
        PillowImageEncoder(),
        storage,
        probe,
        settings.temp_directory,
        ImageEncoderConfig(
            settings.image_min_target_size_bytes,
            settings.image_max_target_size_bytes,
            settings.image_min_quality,
            settings.image_max_quality,
            settings.image_target_search_max_attempts,
            settings.image_target_resize_max_attempts,
            settings.image_target_resize_factor,
            settings.image_target_min_dimension,
            settings.image_best_quality_default,
            settings.image_balanced_quality_default,
            settings.image_smallest_quality_default,
            settings.image_target_min_quality_default,
            settings.image_png_lossless_quality_threshold,
            settings.image_png_palette_quality_thresholds,
            settings.image_png_palette_colors,
        ),
    )
    _process_image_job(UUID(job_id), job_service, service)


def _process_image_job(job_id: UUID, job_service: JobService, service: ImageCompressionService) -> None:
    output_storage_key: str | None = None
    try:
        if job_service.get(job_id).status is JobStatus.CANCELLED:
            return
        logger.info("job_started", extra={"event": "job_started", "job_id": str(job_id), "tool": "image"})
        job_service.transition(job_id, JobStatus.PROBING, progress=5, stage="probing", message="Inspecting image")
        input_metadata = service.probe_input(job_service.get(job_id))
        job_service.set_input_metadata(job_id, asdict(input_metadata))
        if job_service.get(job_id).status is JobStatus.CANCELLED:
            return
        job_service.transition(job_id, JobStatus.PROCESSING, progress=20, stage="encoding", message="Compressing image")
        outcome = service.compress(
            job_service.get(job_id),
            input_metadata,
            on_progress=lambda progress: job_service.update_progress(job_id, progress, "target_search", "Optimizing image"),
        )
        output_storage_key = outcome.output_storage_key
        if job_service.get(job_id).status is JobStatus.CANCELLED:
            service.discard_output(output_storage_key)
            return
        metadata = dict(outcome.output_metadata)
        metadata["size_reduction_percent"] = outcome.size_reduction_percent
        job_service.set_output(job_id, outcome.output_storage_key, metadata)
        job_service.transition(job_id, JobStatus.COMPLETED, progress=100, stage="completed", message="Image ready")
        completed = job_service.get(job_id)
        logger.info("job_completed", extra={"event": "job_completed", "job_id": str(job_id), "tool": "image", "input_bytes": (completed.input_metadata or {}).get("size_bytes"), "output_bytes": (completed.output_metadata or {}).get("size_bytes"), "compression_ratio": (completed.output_metadata or {}).get("size_reduction_percent")})
    except ImageTargetSizeUnreachable as exc:
        if output_storage_key is not None:
            service.discard_output(output_storage_key)
        context = {
            "requested_target_bytes": exc.context.requested_target_bytes,
            "smallest_achieved_bytes": exc.context.smallest_achieved_bytes,
            "smallest_width": exc.context.smallest_width,
            "smallest_height": exc.context.smallest_height,
            "output_format": exc.context.output_format,
            "quality_floor_was_explicit": exc.context.quality_floor_was_explicit,
            "resize_allowed": exc.context.resize_allowed,
        }
        job_service.set_target_failure_context(job_id, context)
        _mark_failed(
            job_service,
            job_id,
            exc.error_code,
            f"We couldn’t reach {round(exc.context.requested_target_bytes / 1024)} KB with the selected format and limits.",
        )
    except ImageEncodingError as exc:
        if output_storage_key is not None:
            service.discard_output(output_storage_key)
        _mark_failed(job_service, job_id, exc.error_code)
    except ApplicationError as exc:
        if output_storage_key is not None:
            service.discard_output(output_storage_key)
        _mark_failed(job_service, job_id, exc.code)
    except Exception:
        if output_storage_key is not None:
            service.discard_output(output_storage_key)
        logger.exception("Image compression worker failed for job %s", job_id)
        _mark_failed(job_service, job_id, "image_processing_failed")
        raise


def _mark_failed(
    job_service: JobService,
    job_id: UUID,
    error_code: str,
    safe_error_message: str = "Image processing could not be completed.",
) -> None:
    try:
        job = job_service.get(job_id)
        if job.status not in {JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.EXPIRED}:
            job_service.transition(job_id, JobStatus.FAILED, stage="failed", message="Image processing failed", error_code=error_code, safe_error_message=safe_error_message)
    except ApplicationError:
        logger.exception("Could not mark image job failed: %s", job_id)
