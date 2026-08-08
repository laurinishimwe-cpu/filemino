from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.models.job import Job, JobStatus, is_valid_transition, utc_now
from app.models.video import CompressionMode, ResolutionOption
from app.queue.base import JobQueue
from app.repositories.job_repository import JobRepository
from app.utils.files import generate_storage_key, original_filename_metadata
from app.services.rate_limit_service import RateLimitService
from app.services.processing_selection_service import ProcessingSelectionService
import logging
logger=logging.getLogger(__name__)


class JobService:
    def __init__(self, repository: JobRepository, queue: JobQueue | None = None, limiter: RateLimitService | None = None, max_jobs_per_hour:int=0, max_concurrent_jobs:int=0, job_ttl_seconds:int=86400, selector:ProcessingSelectionService|None=None) -> None:
        self._repository = repository
        self._queue = queue
        self._limiter=limiter; self._max_jobs=max_jobs_per_hour; self._max_concurrent=max_concurrent_jobs; self._job_ttl=job_ttl_seconds
        self._selector=selector

    def create_video_job(
        self,
        original_filename: str,
        compression_mode: CompressionMode | None,
        target_size_bytes: int | None,
        resolution: ResolutionOption | None,
        input_metadata: dict | None = None,
        input_storage_key: str | None = None,
        client_hash: str | None = None,
        route_by_metadata: bool = False,
    ) -> Job:
        job = Job(
            original_filename=original_filename_metadata(original_filename),
            input_storage_key=input_storage_key or generate_storage_key(),
            compression_mode=compression_mode or CompressionMode.BALANCED,
            target_size_bytes=target_size_bytes,
            resolution=resolution or ResolutionOption.ORIGINAL,
            input_metadata=input_metadata,
        )
        job.client_hash=client_hash
        if self._selector and route_by_metadata:
            job.processing_queue = self._selector.select(input_metadata)
        if client_hash and self._limiter:
            self._limiter.consume_job_request(client_hash,self._max_jobs)
            self._limiter.claim_concurrent(client_hash,job.id,self._max_concurrent,self._job_ttl)
        self._repository.create(job)
        logger.info("job_queued",extra={"event":"job_queued","job_id":str(job.id),"input_bytes":(input_metadata or {}).get("size_bytes")})
        if self._queue is not None:
            self._queue.enqueue_compression(job.id,job.processing_queue)
        return job

    def get(self, job_id: UUID) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise NotFoundError()
        return job

    def transition(
        self,
        job_id: UUID,
        status: JobStatus,
        *,
        progress: int | None = None,
        stage: str | None = None,
        message: str | None = None,
        error_code: str | None = None,
        safe_error_message: str | None = None,
    ) -> Job:
        job = self.get(job_id)
        if not is_valid_transition(job.status, status):
            raise ValidationError("Invalid job state transition.")
        job.status = status
        job.updated_at = utc_now()
        if progress is not None:
            job.progress = _safe_progress(progress)
        if stage is not None:
            job.stage = stage
        if message is not None:
            job.message = message
        job.error_code = error_code
        job.safe_error_message = safe_error_message
        if status is JobStatus.PROCESSING and job.processing_started_at is None:
            job.processing_started_at = job.updated_at
        if status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            job.completed_at = job.updated_at
            if job.client_hash and self._limiter:self._limiter.release_concurrent(job.client_hash,job.id)
        return self._repository.save(job)

    def update_progress(self, job_id: UUID, progress: int, stage: str, message: str) -> Job:
        job = self.get(job_id)
        if job.status not in {JobStatus.PROBING, JobStatus.PROCESSING}:
            raise ValidationError("Only active jobs can report progress.")
        job.progress = _safe_progress(progress)
        job.stage = stage
        job.message = message
        job.updated_at = utc_now()
        return self._repository.save(job)

    def set_input_metadata(self, job_id: UUID, metadata: dict) -> Job:
        job = self.get(job_id)
        job.input_metadata = metadata
        job.updated_at = utc_now()
        return self._repository.save(job)

    def set_output(self, job_id: UUID, output_storage_key: str, metadata: dict) -> Job:
        job = self.get(job_id)
        job.output_storage_key = output_storage_key
        job.output_metadata = metadata
        job.updated_at = utc_now()
        return self._repository.save(job)

    def cancel(self, job_id: UUID) -> Job:
        job = self.get(job_id)
        if job.status is JobStatus.CANCELLED:
            return job
        if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.EXPIRED}:
            raise ValidationError("This job can no longer be cancelled.")
        if job.status is JobStatus.QUEUED and self._queue is not None:
            self._queue.cancel(job_id)
        return self.transition(job_id, JobStatus.CANCELLED, stage="cancelled", message="Job cancelled")


def _safe_progress(value: int) -> int:
    if not 0 <= value <= 100:
        raise ValidationError("Progress must be between 0 and 100.")
    return value
