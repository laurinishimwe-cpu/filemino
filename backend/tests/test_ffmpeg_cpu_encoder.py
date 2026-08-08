import shutil
import subprocess
from pathlib import Path

import pytest

from app.encoders.base import EncodingError, EncodingRequest, TargetSizeError
from app.encoders.ffmpeg_cpu import (
    CPU_PRESETS,
    FFmpegCPUEncoder,
    _parse_progress_line,
    _progress_time_seconds,
    calculate_target_video_bitrate,
)
from app.models.video import CompressionMode, ResolutionOption
from app.models.job import Job
from app.models.video import VideoMetadata, VideoStreamMetadata
from app.services.compression_service import CompressionService
from app.services.video_probe_service import VideoProbeService
from app.storage.local import LocalStorage


def request(mode: CompressionMode = CompressionMode.BALANCED, resolution: ResolutionOption = ResolutionOption.ORIGINAL, target_size_bytes: int | None = None) -> EncodingRequest:
    return EncodingRequest(
        source=Path("input.mp4"),
        destination=Path("output.mp4"),
        duration_seconds=60,
        mode=mode,
        resolution=resolution,
        target_size_bytes=target_size_bytes,
    )


def test_cpu_presets_are_centralized_and_balanced_uses_crf() -> None:
    command = FFmpegCPUEncoder("ffmpeg", 60).build_command(request())

    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[command.index("-crf") + 1] == str(CPU_PRESETS[CompressionMode.BALANCED].crf)
    assert command[-2:] == ["mp4", "output.mp4"]


@pytest.mark.parametrize("mode", [CompressionMode.BEST_QUALITY, CompressionMode.SMALLEST_SIZE])
def test_each_compression_mode_uses_its_central_preset(mode: CompressionMode) -> None:
    command = FFmpegCPUEncoder("ffmpeg", 60).build_command(request(mode=mode))

    assert command[command.index("-crf") + 1] == str(CPU_PRESETS[mode].crf)
    assert command[command.index("-preset") + 1] == CPU_PRESETS[mode].preset


def test_resolution_filter_downscales_without_upscaling() -> None:
    encoder = FFmpegCPUEncoder("ffmpeg", 60)
    command = encoder.build_command(request(resolution=ResolutionOption.HD_1080))

    assert command[command.index("-vf") + 1] == "scale=-2:trunc(min(ih\\,1080)/2)*2"
    assert "-vf" not in encoder.build_command(request())


def test_target_size_derives_positive_video_bitrate() -> None:
    bitrate = calculate_target_video_bitrate(10_000_000, 60, 128_000)
    command = FFmpegCPUEncoder("ffmpeg", 60).build_command(request(target_size_bytes=10_000_000))

    assert bitrate > 0
    assert command[command.index("-b:v") + 1] == str(bitrate)
    assert "-crf" not in command


@pytest.mark.parametrize("size,duration", [(0, 60), (1, 60), (10_000_000, 0)])
def test_impossible_target_sizes_are_rejected(size: int, duration: float) -> None:
    with pytest.raises(TargetSizeError):
        calculate_target_video_bitrate(size, duration, 128_000)


def test_structured_ffmpeg_progress_parsing() -> None:
    assert _parse_progress_line("out_time_us=30000000\n") == ("out_time_us", "30000000")
    assert _progress_time_seconds("out_time_us", "30000000") == 30
    assert _progress_time_seconds("out_time", "00:00:30.000000") == 30


def test_ffmpeg_failure_is_reported_as_an_encoder_error(monkeypatch, tmp_path: Path) -> None:
    class FailedProcess:
        stdout = iter(["progress=end\n"])
        stderr = type("ErrorOutput", (), {"read": lambda self: "invalid input"})()

        def poll(self):
            return 1

        def wait(self, timeout=None):
            return 1

    monkeypatch.setattr("app.encoders.ffmpeg_cpu.subprocess.Popen", lambda *args, **kwargs: FailedProcess())

    with pytest.raises(EncodingError) as error:
        FFmpegCPUEncoder("ffmpeg", 60).compress(request(), lambda _: None, lambda: False)

    assert error.value.error_code == "encoding_failed"


def test_failed_encoding_cleans_temporary_intermediate_files(tmp_path: Path) -> None:
    class FailingEncoder:
        def compress(self, encoding_request, on_progress, is_cancelled) -> None:
            encoding_request.destination.write_bytes(b"partial")
            raise RuntimeError("encoder failed")

    class UnusedProbeService:
        pass

    storage = LocalStorage(tmp_path)
    source_key = "uploads/source.mp4"
    source_path = tmp_path / source_key
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"input")
    compression = CompressionService(FailingEncoder(), storage, UnusedProbeService(), tmp_path)
    job = Job(input_storage_key=source_key)
    metadata = VideoMetadata("source.mp4", 5, 1, "mp4", None, VideoStreamMetadata())

    with pytest.raises(RuntimeError, match="encoder failed"):
        compression.compress(job, metadata, lambda _: None, lambda: False)

    assert not [path for path in tmp_path.iterdir() if path.is_dir() and path.name != "uploads"]


@pytest.mark.integration
def test_small_real_encode_and_probe_when_media_tools_are_available(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("FFmpeg and ffprobe are required for integration tests")
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2", "-shortest",
            "-c:v", "libx264", "-c:a", "aac", str(source),
        ],
        check=True,
        capture_output=True,
    )
    storage = LocalStorage(tmp_path / "storage")
    probe = VideoProbeService(storage, ffprobe, 10_000_000, 30, scratch_directory=tmp_path / "scratch")
    source_metadata = probe.probe(source)
    storage.put(source, "uploads/source.mp4")
    compression = CompressionService(FFmpegCPUEncoder(ffmpeg, 60), storage, probe, tmp_path / "scratch")
    outcome = compression.compress(
        Job(input_storage_key="uploads/source.mp4", resolution=ResolutionOption.HD_720),
        source_metadata,
        lambda _: None,
        lambda: False,
    )
    assert storage.object_info(outcome.output_storage_key) is not None
    output_path = storage.download_to(outcome.output_storage_key, tmp_path / "output.mp4")
    output_metadata = probe.probe(output_path)
    assert output_path.stat().st_size > 0
    assert output_metadata.video.codec == "h264"
    assert output_metadata.video.width == 320
    assert output_metadata.video.height == 240
    assert output_metadata.duration_seconds is not None
    assert abs(output_metadata.duration_seconds - source_metadata.duration_seconds) < 0.25
    assert not [path for path in (tmp_path / "scratch").iterdir() if path.is_dir()]
