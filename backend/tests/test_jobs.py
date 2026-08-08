from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_image_upload_service, get_job_service
from app.core.exceptions import NotFoundError, ValidationError
from app.main import app
from app.models.image import ImageCompressionMode, ImageOutputFormat, ImageResizeOption, JobTool
from app.models.job import Job, JobStatus
from app.models.video import CompressionMode, ResolutionOption, VideoMetadata, VideoStreamMetadata
from app.repositories.job_repository import RedisJobRepository, InMemoryJobRepository, _job_from_payload, _job_to_payload
from app.services.job_service import JobService
from app.services.compression_service import CompressionOutcome
from app.services.processing_selection_service import ProcessingSelectionService
from app.workers.compression_worker import process_compression_job


class RecordingQueue:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []
        self.queue_names: list[str] = []
        self.image_enqueued: list[UUID] = []
        self.image_queue_names: list[str] = []
        self.cancelled: list[UUID] = []

    def enqueue_compression(self, job_id: UUID, queue_name: str = "video-cpu") -> None:
        self.enqueued.append(job_id)
        self.queue_names.append(queue_name)

    def enqueue_image_compression(self, job_id: UUID, queue_name: str = "image-cpu") -> None:
        self.image_enqueued.append(job_id)
        self.image_queue_names.append(queue_name)

    def cancel(self, job_id: UUID) -> bool:
        self.cancelled.append(job_id)
        return True


class JsonRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int) -> None:
        self.values[key] = value

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


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


def test_image_job_uses_its_dedicated_queue_and_tool_metadata() -> None:
    repository = InMemoryJobRepository()
    queue = RecordingQueue()
    service = JobService(repository, queue, image_queue_name="image-cpu")

    job = service.create_image_job(
        "photo.jpg",
        ImageCompressionMode.BALANCED,
        None,
        ImageOutputFormat.ORIGINAL,
        ImageResizeOption.KEEP_ORIGINAL,
        input_metadata={"size_bytes": 1234, "format": "JPEG"},
    )

    assert job.tool is JobTool.IMAGE_COMPRESSION
    assert job.processing_queue == "image-cpu"
    assert queue.image_enqueued == [job.id]
    assert queue.image_queue_names == ["image-cpu"]
    assert queue.enqueued == []


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


def test_cancellation_marks_queued_image_job_and_cancels_its_rq_job() -> None:
    service, _, queue = build_service()
    job = service.create_image_job(
        "photo.jpg",
        ImageCompressionMode.BALANCED,
        None,
        ImageOutputFormat.ORIGINAL,
        ImageResizeOption.KEEP_ORIGINAL,
    )

    cancelled = service.cancel(job.id)

    assert cancelled.status is JobStatus.CANCELLED
    assert queue.image_enqueued == [job.id]
    assert queue.cancelled == [job.id]


def test_redis_record_serialization_round_trip() -> None:
    job = Job(original_filename="sample.mp4", input_storage_key="uploads/safe-id")

    restored = _job_from_payload(_job_to_payload(job))

    assert restored.id == job.id
    assert restored.status is JobStatus.QUEUED
    assert restored.input_storage_key == "uploads/safe-id"


@pytest.mark.parametrize("mode", list(ImageCompressionMode))
def test_image_job_redis_record_serialization_round_trip(mode: ImageCompressionMode) -> None:
    job = Job(
        tool=JobTool.IMAGE_COMPRESSION,
        original_filename="photo.jpg",
        input_storage_key="uploads/safe-id",
        compression_mode=mode,
        target_size_bytes=50 * 1024,
        image_output_format=ImageOutputFormat.WEBP,
        image_resize=ImageResizeOption.PERCENT_75,
    )

    repository = RedisJobRepository(JsonRedis(), ttl_seconds=60)  # type: ignore[arg-type]
    repository.create(job)
    restored = repository.get(job.id)

    assert restored is not None
    assert restored.tool is JobTool.IMAGE_COMPRESSION
    assert type(restored.compression_mode) is ImageCompressionMode
    assert restored.compression_mode is mode
    assert restored.image_output_format is ImageOutputFormat.WEBP
    assert restored.image_resize is ImageResizeOption.PERCENT_75


@pytest.mark.parametrize("mode", list(CompressionMode))
def test_video_job_redis_record_serialization_round_trip(mode: CompressionMode) -> None:
    job = Job(
        tool=JobTool.VIDEO_COMPRESSION,
        original_filename="sample.mp4",
        input_storage_key="uploads/safe-id",
        compression_mode=mode,
    )

    repository = RedisJobRepository(JsonRedis(), ttl_seconds=60)  # type: ignore[arg-type]
    repository.create(job)
    restored = repository.get(job.id)

    assert restored is not None
    assert restored.tool is JobTool.VIDEO_COMPRESSION
    assert type(restored.compression_mode) is CompressionMode
    assert restored.compression_mode is mode


def test_job_rejects_a_mode_from_another_tool_domain() -> None:
    with pytest.raises(ValueError, match="Image jobs require image compression modes"):
        Job(
            tool=JobTool.IMAGE_COMPRESSION,
            original_filename="photo.jpg",
            input_storage_key="uploads/safe-id",
            compression_mode=CompressionMode.BALANCED,
        )


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


def test_image_job_api_contract_uses_an_opaque_upload_id() -> None:
    service, _, _ = build_service()
    upload_id = UUID("00000000-0000-0000-0000-000000000001")

    class ImageUploadService:
        def __init__(self) -> None:
            self.upload_id: UUID | None = None

        def complete_image_upload(
            self,
            received_upload_id: UUID,
            _: JobService,
            compression_mode: ImageCompressionMode,
            target_size_bytes: int | None,
            output_format: ImageOutputFormat,
            resize: ImageResizeOption,
            *extra: object,
        ) -> Job:
            self.upload_id = received_upload_id
            return Job(
                tool=JobTool.IMAGE_COMPRESSION,
                original_filename="photo.jpg",
                input_storage_key="uploads/server-owned-key",
                compression_mode=compression_mode,
                target_size_bytes=target_size_bytes,
                image_output_format=output_format,
                image_resize=resize,
            )

    upload_service = ImageUploadService()
    app.dependency_overrides[get_job_service] = lambda: service
    app.dependency_overrides[get_image_upload_service] = lambda: upload_service
    try:
        response = TestClient(app).post(
            "/api/v1/images/jobs",
            json={
                "upload_id": str(upload_id),
                "compression_mode": "target_size",
                "target_size_bytes": 50 * 1024,
                "output_format": "webp",
                "resize": "75_percent",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert upload_service.upload_id == upload_id
    assert response.json()["tool"] == "image_compression"
    assert "input_storage_key" not in response.json()
