from app.models.job import JobStatus
from app.models.video import CompressionMode, ResolutionOption, VideoMetadata


def test_job_status_values_are_stable() -> None:
    assert [status.value for status in JobStatus] == [
        "queued", "probing", "processing", "completed", "failed", "cancelled", "expired",
    ]


def test_video_domain_models_are_independent_of_http() -> None:
    metadata = VideoMetadata(duration_seconds=12.5, width=1920, height=1080, mime_type="video/mp4")

    assert CompressionMode.BALANCED.value == "balanced"
    assert ResolutionOption.HD_1080.value == "1080"
    assert metadata.width == 1920
