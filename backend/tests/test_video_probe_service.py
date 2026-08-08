from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes.videos import get_video_probe_service
from app.core.exceptions import FileTooLargeError, InvalidVideoError, ProbeError
from app.main import app
from app.services.video_probe_service import VideoProbeService
from app.storage.local import LocalStorage
from app.utils.ffmpeg import parse_ffprobe_json


def valid_payload(with_audio: bool = True) -> dict[str, Any]:
    streams: list[dict[str, Any]] = [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "avg_frame_rate": "30000/1001",
            "pix_fmt": "yuv420p",
            "bit_rate": "9500000",
        }
    ]
    if with_audio:
        streams.append(
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "bit_rate": "128000",
                "sample_rate": "48000",
                "channels": 2,
            }
        )
    return {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "312.4", "bit_rate": "9628000"},
        "streams": streams,
    }


def service(tmp_path: Path, payload: dict[str, Any] | None = None) -> VideoProbeService:
    def runner(_: str, __: Path, ___: int) -> dict[str, Any]:
        return payload if payload is not None else valid_payload()

    return VideoProbeService(LocalStorage(tmp_path), "ffprobe", max_upload_size_bytes=1024, timeout_seconds=5, probe_runner=runner)


def test_probe_extracts_clean_metadata_and_fractional_fps(tmp_path: Path) -> None:
    metadata = service(tmp_path).probe_upload(BytesIO(b"video-data"), "sample.mp4")

    assert metadata.filename == "sample.mp4"
    assert metadata.size_bytes == len(b"video-data")
    assert metadata.container == "mov,mp4,m4a,3gp,3g2,mj2"
    assert metadata.video.codec == "h264"
    assert metadata.video.fps == pytest.approx(29.97002997003)
    assert metadata.audio is not None
    assert metadata.audio.sample_rate == 48_000


def test_probe_allows_missing_audio_metadata(tmp_path: Path) -> None:
    metadata = service(tmp_path, valid_payload(with_audio=False)).probe_upload(BytesIO(b"video-data"), "silent.webm")

    assert metadata.audio is None


def test_malformed_ffprobe_json_raises_safe_probe_error() -> None:
    with pytest.raises(ProbeError):
        parse_ffprobe_json("not json")


def test_invalid_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidVideoError):
        service(tmp_path).probe(tmp_path / "missing.mp4")


def test_ffprobe_payload_without_a_video_stream_is_invalid(tmp_path: Path) -> None:
    with pytest.raises(InvalidVideoError):
        service(tmp_path, {"format": {}, "streams": []}).probe_upload(BytesIO(b"not-a-video"), "sample.mp4")


def test_oversized_upload_is_rejected_and_removed(tmp_path: Path) -> None:
    with pytest.raises(FileTooLargeError):
        service(tmp_path).probe_upload(BytesIO(b"x" * 1025), "large.mp4")

    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


def test_failed_probe_removes_temporary_file(tmp_path: Path) -> None:
    def failing_runner(_: str, __: Path, ___: int) -> dict[str, Any]:
        raise ProbeError()

    probe_service = VideoProbeService(LocalStorage(tmp_path), "ffprobe", 1024, 5, failing_runner)

    with pytest.raises(ProbeError):
        probe_service.probe_upload(BytesIO(b"video-data"), "sample.mp4")

    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


def test_probe_endpoint_returns_the_clean_metadata_contract(tmp_path: Path) -> None:
    app.dependency_overrides[get_video_probe_service] = lambda: service(tmp_path)
    try:
        response = TestClient(app).post(
            "/api/v1/videos/probe",
            files={"file": ("sample.mp4", b"video-data", "video/mp4")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["filename"] == "sample.mp4"
    assert response.json()["video"]["fps"] == pytest.approx(29.97002997003)
