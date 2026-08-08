from uuid import UUID

from redis import Redis
from rq import Queue
from rq.job import Job as RQJob

from app.queue.base import JobQueue


class RedisRQQueue(JobQueue):
    def __init__(self, redis_client: Redis, queue_name: str, gpu_queue_name: str = "video-gpu", image_queue_name: str = "image-cpu") -> None:
        self._redis = redis_client
        self._queue = Queue(queue_name, connection=redis_client)
        self._gpu_queue_name = gpu_queue_name
        self._image_queue_name = image_queue_name

    def enqueue_compression(self, job_id: UUID, queue_name: str = "video-cpu") -> None:
        queue = Queue(queue_name, connection=self._redis)
        worker = "app.workers.compression_worker.run_gpu_compression_job" if queue_name == self._gpu_queue_name else "app.workers.compression_worker.run_compression_job"
        queue.enqueue(
            worker,
            str(job_id),
            job_id=str(job_id),
        )

    def enqueue_image_compression(self, job_id: UUID, queue_name: str = "image-cpu") -> None:
        queue = Queue(queue_name, connection=self._redis)
        queue.enqueue("app.workers.image_compression_worker.run_image_compression_job", str(job_id), job_id=str(job_id))

    def enqueue_image_conversion(self, job_id: UUID, queue_name: str = "image-cpu") -> None:
        queue = Queue(queue_name, connection=self._redis)
        queue.enqueue("app.workers.image_conversion_worker.run_image_conversion_job", str(job_id), job_id=str(job_id))

    def cancel(self, job_id: UUID) -> bool:
        try:
            rq_job = RQJob.fetch(str(job_id), connection=self._redis)
        except Exception:
            return False
        if rq_job.get_status(refresh=True) not in {"queued", "deferred", "scheduled"}:
            return False
        rq_job.cancel()
        return True
