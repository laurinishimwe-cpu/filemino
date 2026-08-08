from app.models.job import JobStatus
from app.models.video import CompressionMode, ResolutionOption, VideoMetadata, VideoStreamMetadata


def test_job_status_values_are_stable() -> None:
    assert [status.value for status in JobStatus] == [
        "queued", "probing", "processing", "completed", "failed", "cancelled", "expired",
    ]


def test_video_domain_models_are_independent_of_http() -> None:
    metadata = VideoMetadata(
        filename="sample.mp4",
        size_bytes=42,
        duration_seconds=12.5,
        container="mov,mp4,m4a,3gp,3g2,mj2",
        bitrate=None,
        video=VideoStreamMetadata(width=1920, height=1080),
    )

    assert CompressionMode.BALANCED.value == "balanced"
    assert ResolutionOption.HD_1080.value == "1080"
    assert metadata.video.width == 1920
