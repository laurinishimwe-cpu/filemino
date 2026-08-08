from typing import Protocol
from uuid import UUID


class JobQueue(Protocol):
    def enqueue_compression(self, job_id: UUID, queue_name: str = "video-cpu") -> None: ...

    def cancel(self, job_id: UUID) -> bool: ...
