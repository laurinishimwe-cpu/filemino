import os
import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue
from rq.job import Job as RQJob

from app.api.dependencies import get_job_service, get_storage
from app.core.config import get_settings
from app.encoders.base import EncodingCancelled
from app.encoders.ffmpeg_cpu import FFmpegCPUEncoder
from app.main import app
from app.models.job import Job, JobStatus
from app.repositories.job_repository import InMemoryJobRepository, RedisJobRepository
from app.repositories.upload_repository import RedisUploadRepository
from app.schemas.job import JobResponse
from app.services.compression_service import CompressionService
from app.services.job_service import JobService
from app.services.processing_selection_service import ProcessingSelectionService
from app.services.upload_service import UploadService
from app.services.video_probe_service import VideoProbeService
from app.storage.local import LocalStorage
from app.queue.redis_queue import RedisRQQueue
from app.workers.compression_worker import process_compression_job
from app.workers.windows_spawn_worker import WindowsSpawnWorker


def _require_media_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("FFmpeg and ffprobe are required for integration tests")
    return ffmpeg, ffprobe


def _make_video(ffmpeg: str, destination: Path, duration: int = 3) -> None:
    subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=24:duration={duration}",
            "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}", "-shortest",
            "-c:v", "libx264", "-c:a", "aac", str(destination),
        ],
        check=True,
        capture_output=True,
    )


def _rq_diagnostics(queue: Queue, job_id: str, fluxfile_job_status: str | None) -> str:
    """Failure-only test output; never surfaced by the application API."""
    try:
        rq_job = RQJob.fetch(job_id, connection=queue.connection)
        rq_status = rq_job.get_status(refresh=True)
        exception = rq_job.exc_info or "<none>"
    except Exception as exc:
        rq_status = f"unavailable ({type(exc).__name__})"
        exception = "<unavailable>"
    return (
        f"queue={queue.name!r}; rq_status={rq_status!r}; "
        f"queued={queue.get_job_ids()!r}; "
        f"started={queue.started_job_registry.get_job_ids()!r}; "
        f"finished={queue.finished_job_registry.get_job_ids()!r}; "
        f"failed={queue.failed_job_registry.get_job_ids()!r}; "
        f"fluxfile_status={fluxfile_job_status!r}; rq_exception={exception}"
    )


@pytest.mark.integration
def test_corrupt_media_becomes_a_safe_failed_job(tmp_path: Path) -> None:
    ffmpeg, ffprobe = _require_media_tools()
    storage = LocalStorage(tmp_path / "storage")
    storage_root = tmp_path / "storage"
    (storage_root / "uploads").mkdir(parents=True)
    (storage_root / "uploads" / "corrupt.mp4").write_bytes(b"not a video")
    repository = InMemoryJobRepository()
    service = JobService(repository)
    job = repository.create(Job(original_filename="corrupt.mp4", input_storage_key="uploads/corrupt.mp4"))
    probe = VideoProbeService(storage, ffprobe, 10_000_000, 30, scratch_directory=tmp_path / "scratch")
    compression = CompressionService(FFmpegCPUEncoder(ffmpeg, 60), storage, probe, tmp_path / "scratch")

    with pytest.raises(Exception):
        process_compression_job(job.id, service, compression, 0)

    failed = service.get(job.id)
    public = JobResponse.model_validate(failed).model_dump_json()
    assert failed.status is JobStatus.FAILED
    assert failed.safe_error_message == "Video processing could not be completed."
    assert str(storage_root) not in public
    assert "ffmpeg" not in public.lower()
    assert not (tmp_path / "scratch").exists() or not list((tmp_path / "scratch").iterdir())


@pytest.mark.integration
def test_real_cancellation_terminates_the_owned_ffmpeg_process_and_cleans_scratch(tmp_path: Path) -> None:
    ffmpeg, ffprobe = _require_media_tools()
    source = tmp_path / "source.mp4"
    _make_video(ffmpeg, source, duration=15)
    storage = LocalStorage(tmp_path / "storage")
    storage.put(source, "uploads/source.mp4")
    probe = VideoProbeService(storage, ffprobe, 20_000_000, 30, scratch_directory=tmp_path / "scratch")
    metadata = probe.probe(source)
    compression = CompressionService(FFmpegCPUEncoder(ffmpeg, 60), storage, probe, tmp_path / "scratch")
    started_at = time.monotonic()

    with pytest.raises(EncodingCancelled):
        compression.compress(
            Job(input_storage_key="uploads/source.mp4"),
            metadata,
            lambda _: None,
            lambda: time.monotonic() - started_at > 0.1,
        )

    outputs_directory = tmp_path / "storage" / "outputs"
    assert not outputs_directory.exists() or not [path for path in outputs_directory.rglob("*") if path.is_file()]
    assert not (tmp_path / "scratch").exists() or not list((tmp_path / "scratch").iterdir())


@pytest.mark.e2e
def test_local_storage_redis_rq_cpu_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("FLUXFILE_RUN_E2E") != "1":
        pytest.skip("Set FLUXFILE_RUN_E2E=1 to run the Redis/RQ end-to-end test")
    ffmpeg, ffprobe = _require_media_tools()
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        redis.ping()
    except Exception:
        pytest.skip("Redis is not reachable")

    queue_name = f"fluxfile-e2e-{uuid4().hex}"
    monkeypatch.setenv("TEMP_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("FFMPEG_BINARY", ffmpeg)
    monkeypatch.setenv("FFPROBE_BINARY", ffprobe)
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("CPU_QUEUE_NAME", queue_name)
    get_settings.cache_clear()
    settings = get_settings()
    storage = LocalStorage(settings.temp_directory, settings.api_prefix)
    job_repository = RedisJobRepository(redis, settings.job_ttl_seconds)
    queue = RedisRQQueue(redis, queue_name, settings.gpu_queue_name)
    configured_gpu_encoders = {
        encoder.strip() for encoder in settings.gpu_available_encoders.split(",") if encoder.strip()
    }
    selector = ProcessingSelectionService(
        settings.gpu_enabled,
        settings.gpu_min_complexity,
        configured_gpu_encoders,
        settings.cpu_queue_name,
        settings.gpu_queue_name,
    )
    job_service = JobService(job_repository, queue, selector=selector)
    probe = VideoProbeService(storage, ffprobe, 20_000_000, 30, scratch_directory=tmp_path)
    upload_service = UploadService(
        RedisUploadRepository(redis), storage, probe, settings.file_retention_seconds,
        settings.r2_signed_url_expiry_seconds, 20_000_000,
    )
    source = tmp_path / "input.mp4"
    _make_video(ffmpeg, source)
    upload, _ = upload_service.initialize("input.mp4", "video/mp4")
    storage.put(source, upload.storage_key)
    job = upload_service.complete_video_upload(upload.id, job_service)
    assert job.status is JobStatus.QUEUED
    assert job.processing_queue == queue_name
    rq_queue = Queue(queue_name, connection=redis)
    assert str(job.id) in rq_queue.get_job_ids()

    try:
        WindowsSpawnWorker([rq_queue], connection=redis).work(burst=True, logging_level="WARNING")
        completed = job_repository.get(job.id)
        if completed is None or completed.status is not JobStatus.COMPLETED:
            pytest.fail(_rq_diagnostics(rq_queue, str(job.id), None if completed is None else completed.status.value))
        assert completed.progress == 100
        assert completed.processing_started_at is not None
        assert completed.output_storage_key is not None
        assert storage.object_info(completed.output_storage_key) is not None
        assert completed.output_metadata and completed.output_metadata["size_bytes"] > 0
        assert completed.output_metadata["size_reduction_percent"] is not None
        public_json = JobResponse.model_validate(completed).model_dump_json()
        assert "storage_key" not in public_json
        assert str(tmp_path) not in public_json
        app.dependency_overrides[get_job_service] = lambda: job_service
        app.dependency_overrides[get_storage] = lambda: storage
        try:
            client = TestClient(app)
            download = client.get(f"/api/v1/jobs/{job.id}/download")
            content = client.get(download.json()["download_url"])
        finally:
            app.dependency_overrides.clear()
        assert download.status_code == 200
        assert content.status_code == 200 and content.content
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
