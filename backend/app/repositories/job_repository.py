from typing import Protocol
from uuid import UUID

from app.models.job import Job


class JobRepository(Protocol):
    def create(self, job: Job) -> Job: ...

    def get(self, job_id: UUID) -> Job | None: ...

    def save(self, job: Job) -> Job: ...


class InMemoryJobRepository:
    """Development-only repository; replace through the same protocol later."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, Job] = {}

    def create(self, job: Job) -> Job:
        self._jobs[job.id] = job
        return job

    def get(self, job_id: UUID) -> Job | None:
        return self._jobs.get(job_id)

    def save(self, job: Job) -> Job:
        self._jobs[job.id] = job
        return job
