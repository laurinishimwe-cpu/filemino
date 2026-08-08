import logging
import time
from dataclasses import asdict
from uuid import UUID

from redis import Redis

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.encoders.base import EncodingCancelled, EncodingError
from app.encoders.ffmpeg_cpu import FFmpegCPUEncoder
from app.models.job import JobStatus
from app.repositories.job_repository import RedisJobRepository
from app.services.compression_service import CompressionService
from app.services.job_service import JobService
from app.services.video_probe_service import VideoProbeService
from app.storage.factory import create_storage
from app.services.rate_limit_service import RateLimitService
from app.encoders.ffmpeg_nvidia import FFmpegNvidiaEncoder

logger = logging.getLogger(__name__)


def run_compression_job(job_id: str) -> None:
    """RQ entry point for CPU FFmpeg compression."""
    settings = get_settings()
    repository = RedisJobRepository(Redis.from_url(settings.redis_url), settings.job_ttl_seconds)
    job_service = JobService(repository, limiter=RateLimitService(Redis.from_url(settings.redis_url),settings.rate_limit_hash_salt), max_jobs_per_hour=settings.guest_max_jobs_per_hour, max_concurrent_jobs=settings.guest_max_concurrent_jobs, job_ttl_seconds=settings.job_ttl_seconds)
    storage = create_storage(settings)
    probe_service = VideoProbeService(
        storage=storage,
        ffprobe_binary=settings.ffprobe_binary,
        max_upload_size_bytes=settings.max_upload_size_bytes,
        timeout_seconds=settings.ffprobe_timeout_seconds,
        scratch_directory=settings.temp_directory,
    )
    compression_service = CompressionService(
        encoder=FFmpegCPUEncoder(settings.ffmpeg_binary, settings.ffmpeg_timeout_seconds),
        storage=storage,
        probe_service=probe_service,
        temp_directory=settings.temp_directory,
    )
    process_compression_job(
        UUID(job_id),
        job_service,
        compression_service,
        settings.progress_persist_interval_seconds,
    )

def run_gpu_compression_job(job_id:str)->None:
    settings=get_settings()
    if not settings.gpu_enabled:
        if settings.gpu_fallback_to_cpu:
            logger.warning("gpu_fallback_to_cpu", extra={"event": "gpu_fallback_to_cpu", "job_id": job_id, "reason": "disabled"})
            return run_compression_job(job_id)
        raise RuntimeError("GPU processing is disabled")
    try: encoder=FFmpegNvidiaEncoder(settings.ffmpeg_binary,settings.ffmpeg_timeout_seconds)
    except RuntimeError:
        if settings.gpu_fallback_to_cpu:
            logger.warning("gpu_fallback_to_cpu", extra={"event": "gpu_fallback_to_cpu", "job_id": job_id, "reason": "unavailable"})
            return run_compression_job(job_id)
        raise
    logger.info("gpu_encoder_selected", extra={"event": "gpu_encoder_selected", "job_id": job_id, "encoder": "h264_nvenc"})
    repository=RedisJobRepository(Redis.from_url(settings.redis_url),settings.job_ttl_seconds); storage=create_storage(settings)
    service=JobService(repository,limiter=RateLimitService(Redis.from_url(settings.redis_url),settings.rate_limit_hash_salt),max_jobs_per_hour=settings.guest_max_jobs_per_hour,max_concurrent_jobs=settings.guest_max_concurrent_jobs,job_ttl_seconds=settings.job_ttl_seconds)
    probe=VideoProbeService(storage,settings.ffprobe_binary,settings.max_upload_size_bytes,settings.ffprobe_timeout_seconds,scratch_directory=settings.temp_directory)
    process_compression_job(UUID(job_id),service,CompressionService(encoder,storage,probe,settings.temp_directory),settings.progress_persist_interval_seconds)


def process_compression_job(
    job_id: UUID,
    job_service: JobService,
    compression_service: CompressionService,
    progress_persist_interval_seconds: float = 1.0,
) -> None:
    """Orchestrate job state; FFmpeg command details stay inside the encoder."""
    try:
        if job_service.get(job_id).status is JobStatus.CANCELLED:
            return
        logger.info("job_started",extra={"event":"job_started","job_id":str(job_id)})
        job_service.transition(job_id, JobStatus.PROBING, progress=5, stage="probing", message="Inspecting video")
        input_metadata = compression_service.probe_input(job_service.get(job_id))
        job_service.set_input_metadata(job_id, asdict(input_metadata))
        if _is_cancelled(job_service, job_id):
            return
        job_service.transition(job_id, JobStatus.PROCESSING, progress=10, stage="encoding", message="Compressing video")
        progress_callback = _throttled_progress_callback(
            job_service,
            job_id,
            progress_persist_interval_seconds,
        )
        outcome = compression_service.compress(
            job_service.get(job_id),
            input_metadata,
            progress_callback,
            lambda: _is_cancelled(job_service, job_id),
        )
        if _is_cancelled(job_service, job_id):
            return
        output_metadata = dict(outcome.output_metadata)
        output_metadata["size_reduction_percent"] = outcome.size_reduction_percent
        job_service.set_output(job_id, outcome.output_storage_key, output_metadata)
        job_service.transition(job_id, JobStatus.COMPLETED, progress=100, stage="completed", message="Video ready")
        completed=job_service.get(job_id); logger.info("job_completed",extra={"event":"job_completed","job_id":str(job_id),"input_bytes":(completed.input_metadata or {}).get("size_bytes"),"output_bytes":(completed.output_metadata or {}).get("size_bytes"),"compression_ratio":(completed.output_metadata or {}).get("size_reduction_percent")})
    except EncodingCancelled:
        _mark_cancelled(job_service, job_id)
    except EncodingError as exc:
        _mark_failed(job_service, job_id, exc.error_code)
    except Exception:
        logger.exception("Compression worker failed for job %s", job_id)
        _mark_failed(job_service, job_id, "processing_failed")
        raise


def _throttled_progress_callback(
    job_service: JobService,
    job_id: UUID,
    interval_seconds: float,
):
    last_persisted_at = 0.0
    last_progress = 0

    def persist(progress: int) -> None:
        nonlocal last_persisted_at, last_progress
        now = time.monotonic()
        if progress <= last_progress or (now - last_persisted_at < interval_seconds and progress < 99):
            return
        if _is_cancelled(job_service, job_id):
            return
        job_service.update_progress(job_id, progress, "encoding", "Compressing video")
        last_progress = progress
        last_persisted_at = now

    return persist


def _is_cancelled(job_service: JobService, job_id: UUID) -> bool:
    return job_service.get(job_id).status is JobStatus.CANCELLED


def _mark_cancelled(job_service: JobService, job_id: UUID) -> None:
    try:
        job = job_service.get(job_id)
        if job.status is not JobStatus.CANCELLED:
            job_service.transition(job_id, JobStatus.CANCELLED, stage="cancelled", message="Job cancelled")
    except ApplicationError:
        logger.exception("Could not mark cancelled job %s", job_id)


def _mark_failed(job_service: JobService, job_id: UUID, error_code: str) -> None:
    try:
        job = job_service.get(job_id)
        if job.status not in {JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.EXPIRED}:
            job_service.transition(
                job_id,
                JobStatus.FAILED,
                stage="failed",
                message="Video processing failed",
                error_code=error_code,
                safe_error_message="Video processing could not be completed.",
            )
    except ApplicationError:
        logger.exception("Could not mark failed job %s", job_id)
