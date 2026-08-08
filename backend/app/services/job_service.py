from datetime import datetime
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.models.job import Job, JobStatus
from app.repositories.job_repository import JobRepository


class JobService:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    def create(self) -> Job:
        return self._repository.create(Job())

    def get(self, job_id: UUID) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise NotFoundError()
        return job

    def update_status(self, job_id: UUID, status: JobStatus, error_code: str | None = None) -> Job:
        job = self.get(job_id)
        job.status = status
        job.error_code = error_code
        job.updated_at = datetime.utcnow()
        return self._repository.save(job)
