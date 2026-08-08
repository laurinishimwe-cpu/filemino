from typing import Protocol
from uuid import UUID


class JobQueue(Protocol):
    def enqueue_compression(self, job_id: UUID) -> None: ...
