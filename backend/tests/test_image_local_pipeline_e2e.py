import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from redis import Redis
from rq import Queue
from rq.job import Job as RQJob

from app.api.dependencies import get_job_service, get_storage
from app.core.config import get_settings
from app.models.image import ImageCompressionMode, ImageOutputFormat, ImageResizeOption, JobTool
from app.models.job import JobStatus
from app.repositories.job_repository import RedisJobRepository
from app.repositories.upload_repository import RedisUploadRepository
from app.queue.redis_queue import RedisRQQueue
from app.main import app
from app.schemas.job import JobResponse
from app.services.image_probe_service import ImageProbeService
from app.services.job_service import JobService
from app.services.upload_service import UploadService
from app.services.video_probe_service import VideoProbeService
from app.storage.local import LocalStorage
from app.workers.windows_spawn_worker import WindowsSpawnWorker


def _diagnostics(queue: Queue, job_id: str, status: str | None) -> str:
    try:
        rq_job = RQJob.fetch(job_id, connection=queue.connection)
        rq_status, exception = rq_job.get_status(refresh=True), rq_job.exc_info or "<none>"
    except Exception as exc:
        rq_status, exception = f"unavailable ({type(exc).__name__})", "<unavailable>"
    return f"queue={queue.name!r}; rq_status={rq_status!r}; queued={queue.get_job_ids()!r}; started={queue.started_job_registry.get_job_ids()!r}; finished={queue.finished_job_registry.get_job_ids()!r}; failed={queue.failed_job_registry.get_job_ids()!r}; fluxfile_status={status!r}; rq_exception={exception}"


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("image_format", "compression_mode", "target_size_bytes", "output_format"),
    [
        ("JPEG", ImageCompressionMode.TARGET_SIZE, 50 * 1024, ImageOutputFormat.JPEG),
        ("JPEG", ImageCompressionMode.BALANCED, None, ImageOutputFormat.ORIGINAL),
        ("PNG", ImageCompressionMode.BALANCED, None, ImageOutputFormat.ORIGINAL),
    ],
)
def test_local_storage_redis_rq_image_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_format: str,
    compression_mode: ImageCompressionMode,
    target_size_bytes: int | None,
    output_format: ImageOutputFormat,
) -> None:
    if os.environ.get("FLUXFILE_RUN_E2E") != "1":
        pytest.skip("Set FLUXFILE_RUN_E2E=1 to run the Redis/RQ image end-to-end test")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        redis.ping()
    except Exception:
        pytest.skip("Redis is not reachable")

    queue_name = f"fluxfile-image-e2e-{uuid4().hex}"
    monkeypatch.setenv("TEMP_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("IMAGE_QUEUE_NAME", queue_name)
    get_settings.cache_clear()
    settings = get_settings()
    storage = LocalStorage(settings.temp_directory, settings.api_prefix)
    job_repository = RedisJobRepository(redis, settings.job_ttl_seconds)
    queue = RedisRQQueue(redis, settings.cpu_queue_name, settings.gpu_queue_name, queue_name)
    job_service = JobService(job_repository, queue, image_max_jobs_per_hour=100, image_max_concurrent_jobs=10, image_queue_name=queue_name)
    image_probe = ImageProbeService(storage, 20_000_000, 40_000_000, 8_000, 8_000, tmp_path)
    video_probe = VideoProbeService(storage, settings.ffprobe_binary, 20_000_000, settings.ffprobe_timeout_seconds, scratch_directory=tmp_path)
    upload_service = UploadService(RedisUploadRepository(redis), storage, video_probe, settings.file_retention_seconds, settings.r2_signed_url_expiry_seconds, 20_000_000, image_probe_service=image_probe, image_queue_name=queue_name, image_max_upload_size_bytes=20_000_000)
    suffix = ".jpg" if image_format == "JPEG" else ".png"
    content_type = "image/jpeg" if image_format == "JPEG" else "image/png"
    source = tmp_path / f"input{suffix}"
    save_options = {"quality": 95} if image_format == "JPEG" else {}
    Image.effect_noise((640, 480), 90).convert("RGB").save(source, format=image_format, **save_options)
    upload, _ = upload_service.initialize(f"input{suffix}", content_type)
    storage.put(source, upload.storage_key)
    job = upload_service.complete_image_upload(upload.id, job_service, compression_mode, target_size_bytes, output_format, ImageResizeOption.KEEP_ORIGINAL)
    assert job.status is JobStatus.QUEUED
    assert job.tool is JobTool.IMAGE_COMPRESSION
    assert job.processing_queue == queue_name
    rq_queue = Queue(queue_name, connection=redis)
    assert str(job.id) in rq_queue.get_job_ids()

    try:
        WindowsSpawnWorker([rq_queue], connection=redis).work(burst=True, logging_level="WARNING")
        completed = job_repository.get(job.id)
        if completed is None or completed.status is not JobStatus.COMPLETED:
            pytest.fail(_diagnostics(rq_queue, str(job.id), None if completed is None else completed.status.value))
        assert completed.output_storage_key and storage.object_info(completed.output_storage_key) is not None
        assert completed.output_metadata is not None
        if target_size_bytes is not None:
            assert completed.output_metadata["size_bytes"] <= target_size_bytes
            assert completed.output_metadata["target_achieved"] is True
        assert completed.output_metadata["format"] == image_format
        public = JobResponse.model_validate(completed).model_dump_json()
        assert "storage_key" not in public and str(tmp_path) not in public
        app.dependency_overrides[get_job_service] = lambda: job_service
        app.dependency_overrides[get_storage] = lambda: storage
        try:
            client = TestClient(app)
            download = client.get(f"/api/v1/jobs/{job.id}/download")
            content = client.get(download.json()["download_url"])
        finally:
            app.dependency_overrides.clear()
        assert download.status_code == 200
        assert content.status_code == 200 and content.headers["content-type"].startswith(content_type)
    finally:
        latest = job_repository.get(job.id)
        if latest and latest.output_storage_key:
            storage.delete(latest.output_storage_key)
        storage.delete(upload.storage_key)
        job_repository.delete(job.id)
        try:
            RQJob.fetch(str(job.id), connection=redis).delete()
        except Exception:
            pass
        get_settings.cache_clear()
