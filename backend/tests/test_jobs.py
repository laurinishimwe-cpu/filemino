from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_job_service
from app.core.exceptions import NotFoundError, ValidationError
from app.main import app
from app.models.job import Job, JobStatus
from app.models.video import CompressionMode, ResolutionOption, VideoMetadata, VideoStreamMetadata
from app.repositories.job_repository import InMemoryJobRepository, _job_from_payload, _job_to_payload
from app.services.job_service import JobService
from app.services.compression_service import CompressionOutcome
from app.services.processing_selection_service import ProcessingSelectionService
from app.workers.compression_worker import process_compression_job


class RecordingQueue:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []
        self.queue_names: list[str] = []
        self.cancelled: list[UUID] = []

    def enqueue_compression(self, job_id: UUID, queue_name: str = "video-cpu") -> None:
        self.enqueued.append(job_id)
        self.queue_names.append(queue_name)

    def cancel(self, job_id: UUID) -> bool:
        self.cancelled.append(job_id)
        return True


def build_service() -> tuple[JobService, InMemoryJobRepository, RecordingQueue]:
    repository = InMemoryJobRepository()
    queue = RecordingQueue()
    return JobService(repository, queue), repository, queue


def create_job(service: JobService) -> Job:
    return service.create_video_job(
        original_filename="sample.mp4",
        compression_mode=CompressionMode.BALANCED,
        target_size_bytes=None,
        resolution=ResolutionOption.ORIGINAL,
    )


class FakeCompressionService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def probe_input(self, job: Job) -> VideoMetadata:
        if self.fail:
            raise RuntimeError("probe failed")
        return VideoMetadata(
            filename=job.original_filename,
            size_bytes=428_000_000,
            duration_seconds=60,
            container="mov,mp4,m4a,3gp,3g2,mj2",
            bitrate=1_000_000,
            video=VideoStreamMetadata(codec="h264", width=1920, height=1080),
        )

    def compress(self, _: Job, __: VideoMetadata, on_progress, ___) -> CompressionOutcome:
        if self.fail:
            raise RuntimeError("encoding failed")
        on_progress(64)
        return CompressionOutcome(
            output_storage_key="outputs/result.mp4",
            output_metadata={"size_bytes": 126_000_000},
            size_reduction_percent=70,
        )


def test_create_and_retrieve_job() -> None:
    service, _, queue = build_service()
    job = create_job(service)

    assert service.get(job.id).status is JobStatus.QUEUED
    assert queue.enqueued == [job.id]
    assert job.input_storage_key.startswith("uploads/")


def test_only_validated_metadata_can_select_gpu_queue() -> None:
    repository = InMemoryJobRepository()
    queue = RecordingQueue()
    selector = ProcessingSelectionService(True, "heavy", {"h264_nvenc"}, "video-cpu", "video-gpu")
    service = JobService(repository, queue, selector=selector)

    untrusted = service.create_video_job("sample.mp4", None, None, None, {"complexity": "very_heavy"})
    trusted = service.create_video_job(
        "sample.mp4", None, None, None, {"complexity": "very_heavy"}, route_by_metadata=True
    )

    assert untrusted.processing_queue == "video-cpu"
    assert trusted.processing_queue == "video-gpu"
    assert queue.queue_names == ["video-cpu", "video-gpu"]


def test_unknown_job_is_not_found() -> None:
    service, _, _ = build_service()

    with pytest.raises(NotFoundError):
        service.get(UUID("00000000-0000-0000-0000-000000000000"))


def test_valid_and_invalid_state_transitions() -> None:
    service, _, _ = build_service()
    job = create_job(service)

    service.transition(job.id, JobStatus.PROBING)
    service.transition(job.id, JobStatus.PROCESSING)
    completed = service.transition(job.id, JobStatus.COMPLETED, progress=100)

    assert completed.status is JobStatus.COMPLETED
    with pytest.raises(ValidationError):
        service.transition(job.id, JobStatus.PROCESSING)


def test_worker_completes_queued_job() -> None:
    service, _, _ = build_service()
    job = create_job(service)

    process_compression_job(job.id, service, FakeCompressionService(), progress_persist_interval_seconds=0)

    completed = service.get(job.id)
    assert completed.status is JobStatus.COMPLETED
    assert completed.progress == 100
    assert completed.stage == "completed"


def test_worker_marks_job_failed_on_unexpected_error() -> None:
    service, _, _ = build_service()
    job = create_job(service)

    with pytest.raises(RuntimeError):
        process_compression_job(job.id, service, FakeCompressionService(fail=True))

    failed = service.get(job.id)
    assert failed.status is JobStatus.FAILED
    assert failed.error_code == "processing_failed"
    assert failed.safe_error_message == "Video processing could not be completed."


def test_ttl_removes_expired_in_memory_job() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)
    repository = InMemoryJobRepository(ttl_seconds=10, clock=lambda: current)
    job = repository.create(Job())
    current += timedelta(seconds=10)

    assert repository.get(job.id) is None


def test_cancellation_marks_queued_job_and_worker_does_not_process_it() -> None:
    service, _, queue = build_service()
    job = create_job(service)

    cancelled = service.cancel(job.id)
    process_compression_job(job.id, service, FakeCompressionService())

    assert cancelled.status is JobStatus.CANCELLED
    assert queue.cancelled == [job.id]
    assert service.get(job.id).status is JobStatus.CANCELLED


def test_redis_record_serialization_round_trip() -> None:
    job = Job(original_filename="sample.mp4", input_storage_key="uploads/safe-id")

    restored = _job_from_payload(_job_to_payload(job))

    assert restored.id == job.id
    assert restored.status is JobStatus.QUEUED
    assert restored.input_storage_key == "uploads/safe-id"


def test_job_api_contract_uses_injected_service() -> None:
    service, _, _ = build_service()
    app.dependency_overrides[get_job_service] = lambda: service
    try:
        created = TestClient(app).post("/api/v1/videos/jobs", json={"original_filename": "sample.mp4"})
        job_id = created.json()["id"]
        fetched = TestClient(app).get(f"/api/v1/jobs/{job_id}")
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 202
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "queued"
