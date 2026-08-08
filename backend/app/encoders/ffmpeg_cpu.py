import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from app.encoders.base import (
    CancellationCheck,
    EncodingCancelled,
    EncodingError,
    EncodingRequest,
    EncodingTimeoutError,
    ProgressCallback,
    TargetSizeError,
    VideoEncoder,
)
from app.models.video import CompressionMode, ResolutionOption

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CompressionPreset:
    crf: int
    preset: str
    audio_bitrate: int


CPU_PRESETS: dict[CompressionMode, CompressionPreset] = {
    CompressionMode.BEST_QUALITY: CompressionPreset(crf=20, preset="medium", audio_bitrate=160_000),
    CompressionMode.BALANCED: CompressionPreset(crf=23, preset="medium", audio_bitrate=128_000),
    CompressionMode.SMALLEST_SIZE: CompressionPreset(crf=28, preset="slow", audio_bitrate=96_000),
}
MIN_VIDEO_BITRATE = 100_000
TARGET_AUDIO_FRACTION = 0.2


class FFmpegCPUEncoder(VideoEncoder):
    def __init__(self, binary: str, timeout_seconds: int) -> None:
        self._binary = binary
        self._timeout_seconds = timeout_seconds

    def compress(
        self,
        request: EncodingRequest,
        on_progress: ProgressCallback,
        is_cancelled: CancellationCheck,
    ) -> None:
        command = self.build_command(request)
        request.destination.parent.mkdir(parents=True, exist_ok=True)
        started_at = time.monotonic()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise EncodingError() from exc

        try:
            self._consume_progress(process, request.duration_seconds, on_progress, is_cancelled, started_at)
            stderr = process.stderr.read() if process.stderr is not None else ""
            return_code = process.wait()
        except (EncodingCancelled, EncodingTimeoutError):
            self._terminate(process)
            raise

        if return_code != 0:
            logger.warning("FFmpeg failed for %s with exit code %s: %s", request.source.name, return_code, stderr)
            error = EncodingError()
            if "no space left on device" in stderr.lower():
                error.error_code = "insufficient_disk_space"
            raise error

    def build_command(self, request: EncodingRequest) -> list[str]:
        preset = CPU_PRESETS[request.mode]
        command = [
            self._binary, "-y", "-v", "error", "-nostats", "-progress", "pipe:1", "-i", str(request.source),
            "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", preset.preset,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", str(preset.audio_bitrate),
        ]
        scale_filter = _scale_filter(request.resolution)
        if scale_filter is not None:
            command.extend(["-vf", scale_filter])
        if request.target_size_bytes is None:
            command.extend(["-crf", str(preset.crf)])
        else:
            video_bitrate = calculate_target_video_bitrate(
                request.target_size_bytes,
                request.duration_seconds,
                preset.audio_bitrate,
            )
            command.extend(["-b:v", str(video_bitrate), "-maxrate", str(video_bitrate), "-bufsize", str(video_bitrate * 2)])
        command.extend(["-movflags", "+faststart", "-f", "mp4", str(request.destination)])
        return command

    def _consume_progress(
        self,
        process: subprocess.Popen[str],
        duration_seconds: float,
        on_progress: ProgressCallback,
        is_cancelled: CancellationCheck,
        started_at: float,
    ) -> None:
        if process.stdout is None:
            raise EncodingError()
        lines: Queue[str | None] = Queue()

        def read_progress() -> None:
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        reader = Thread(target=read_progress, daemon=True)
        reader.start()
        latest_seconds = 0.0
        while True:
            if is_cancelled():
                raise EncodingCancelled()
            if time.monotonic() - started_at > self._timeout_seconds:
                raise EncodingTimeoutError()
            try:
                line = lines.get(timeout=0.2)
            except Empty:
                if process.poll() is not None:
                    break
                continue
            if line is None:
                break
            key, value = _parse_progress_line(line)
            if key in {"out_time_us", "out_time_ms", "out_time"}:
                parsed = _progress_time_seconds(key, value)
                if parsed is not None:
                    latest_seconds = parsed
                    if duration_seconds > 0:
                        on_progress(min(99, max(0, int(latest_seconds / duration_seconds * 100))))
            if key == "progress" and value == "end":
                on_progress(99)

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def calculate_target_video_bitrate(target_size_bytes: int, duration_seconds: float, audio_bitrate: int) -> int:
    if target_size_bytes <= 0 or duration_seconds <= 0 or audio_bitrate <= 0:
        raise TargetSizeError()
    total_bitrate = int(target_size_bytes * 8 / duration_seconds)
    reserved_audio = min(audio_bitrate, max(32_000, int(total_bitrate * TARGET_AUDIO_FRACTION)))
    video_bitrate = total_bitrate - reserved_audio
    if video_bitrate < MIN_VIDEO_BITRATE:
        raise TargetSizeError()
    return video_bitrate


def _scale_filter(resolution: ResolutionOption) -> str | None:
    max_height = {
        ResolutionOption.ORIGINAL: None,
        ResolutionOption.HD_1080: 1080,
        ResolutionOption.HD_720: 720,
        ResolutionOption.SD_480: 480,
    }[resolution]
    if max_height is None:
        return None
    return f"scale=-2:trunc(min(ih\\,{max_height})/2)*2"


def _parse_progress_line(line: str) -> tuple[str, str]:
    return tuple(line.strip().split("=", maxsplit=1)) if "=" in line else ("", "")


def _progress_time_seconds(key: str, value: str) -> float | None:
    try:
        if key in {"out_time_us", "out_time_ms"}:
            return int(value) / 1_000_000
        if key == "out_time":
            hours, minutes, seconds = value.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return None
    return None
