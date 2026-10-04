from uuid import uuid4

import pytest

from app.queue import redis_queue
from app.queue.redis_queue import RedisRQQueue


class RecordingQueue:
    enqueued: list[tuple[str, tuple, dict]] = []

    def __init__(self, name: str, connection: object) -> None:
        self.name = name

    def enqueue(self, func: str, *args: object, **kwargs: object) -> None:
        self.enqueued.append((self.name, (func, *args), kwargs))


@pytest.fixture
def recorded(monkeypatch) -> list[tuple[str, tuple, dict]]:
    RecordingQueue.enqueued = []
    monkeypatch.setattr(redis_queue, "Queue", RecordingQueue)
    return RecordingQueue.enqueued


@pytest.mark.parametrize("queue_name", ["video-cpu", "video-gpu"])
def test_video_jobs_use_configured_timeout(recorded, queue_name: str) -> None:
    queue = RedisRQQueue(object(), "video-cpu", "video-gpu", "image-cpu", video_job_timeout=3_900)
    job_id = uuid4()

    queue.enqueue_compression(job_id, queue_name)

    name, args, kwargs = recorded[-1]
    assert name == queue_name
    assert args[1] == str(job_id)
    assert kwargs == {"job_id": str(job_id), "job_timeout": 3_900}


def test_video_jobs_keep_rq_default_timeout_when_not_configured(recorded) -> None:
    queue = RedisRQQueue(object(), "video-cpu")

    queue.enqueue_compression(uuid4())

    assert recorded[-1][2]["job_timeout"] is None


def test_api_queue_allows_video_jobs_to_outlast_ffmpeg_timeout(monkeypatch) -> None:
    from app.api import dependencies

    captured: dict[str, object] = {}

    class CapturingQueue:
        def __init__(self, *args: object, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(dependencies, "RedisRQQueue", CapturingQueue)
    settings = dependencies.get_settings()

    dependencies.get_job_service()

    assert captured["video_job_timeout"] > settings.ffmpeg_timeout_seconds
