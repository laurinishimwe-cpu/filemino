import logging
import math
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, BinaryIO

from app.core.exceptions import FileTooLargeError, InvalidVideoError, ProbeError, UnsupportedMediaError
from app.models.video import AudioStreamMetadata, VideoMetadata, VideoStreamMetadata
from app.storage.base import FileStorage
from app.utils.ffmpeg import execute_ffprobe
from app.utils.files import generate_storage_key, original_filename_metadata

logger = logging.getLogger(__name__)

ProbeRunner = Callable[[str, Path, int], dict[str, Any]]
SUPPORTED_VIDEO_EXTENSIONS = {".3gp", ".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}


class VideoProbeService:
    def __init__(
        self,
        storage: FileStorage,
        ffprobe_binary: str,
        max_upload_size_bytes: int,
        timeout_seconds: int,
        probe_runner: ProbeRunner = execute_ffprobe,
        scratch_directory: Path | None = None,
    ) -> None:
        self._storage = storage
        self._ffprobe_binary = ffprobe_binary
        self._max_upload_size_bytes = max_upload_size_bytes
        self._timeout_seconds = timeout_seconds
        self._probe_runner = probe_runner
        self._scratch_directory = scratch_directory

    def probe_upload(self, stream: BinaryIO, original_filename: str | None) -> VideoMetadata:
        filename = original_filename_metadata(original_filename or "upload")
        self._reject_obviously_unsupported(filename)
        object_key = generate_storage_key()
        try:
            try:
                size_bytes = self._storage.put_stream(stream, object_key, self._max_upload_size_bytes)
            except ValueError as exc:
                raise FileTooLargeError() from exc
            if size_bytes == 0:
                raise InvalidVideoError()
            with tempfile.TemporaryDirectory(dir=self._scratch_directory) as workspace:
                source = self._storage.download_to(object_key, Path(workspace) / "probe-input")
                return self.probe(source, filename=filename, size_bytes=size_bytes)
        finally:
            self._storage.delete(object_key)

    def probe(self, source: Path, filename: str | None = None, size_bytes: int | None = None) -> VideoMetadata:
        if not source.is_file():
            raise InvalidVideoError()
        actual_size = source.stat().st_size if size_bytes is None else size_bytes
        if actual_size == 0:
            raise InvalidVideoError()
        if actual_size > self._max_upload_size_bytes:
            raise FileTooLargeError()

        payload = self._probe_runner(self._ffprobe_binary, source, self._timeout_seconds)
        try:
            return self._metadata_from_payload(payload, filename or source.name, actual_size)
        except (TypeError, ValueError, KeyError) as exc:
            logger.info("Could not parse ffprobe metadata for %s: %s", source.name, exc)
            raise ProbeError() from exc

    def probe_storage(self, object_key: str, filename: str, size_bytes: int) -> VideoMetadata:
        with tempfile.TemporaryDirectory(dir=self._scratch_directory) as workspace:
            source = self._storage.download_to(object_key, Path(workspace) / "probe-input")
            return self.probe(source, filename=filename, size_bytes=size_bytes)

    def _metadata_from_payload(self, payload: Mapping[str, Any], filename: str, size_bytes: int) -> VideoMetadata:
        streams = payload.get("streams")
        if not isinstance(streams, list):
            raise ProbeError()
        video_stream = next((stream for stream in streams if isinstance(stream, Mapping) and stream.get("codec_type") == "video"), None)
        if video_stream is None:
            raise InvalidVideoError()
        audio_stream = next((stream for stream in streams if isinstance(stream, Mapping) and stream.get("codec_type") == "audio"), None)
        format_data = payload.get("format") if isinstance(payload.get("format"), Mapping) else {}
        return VideoMetadata(
            filename=filename,
            size_bytes=size_bytes,
            duration_seconds=_to_float(format_data.get("duration")),
            container=_to_str(format_data.get("format_name")),
            bitrate=_to_int(format_data.get("bit_rate")),
            video=VideoStreamMetadata(
                codec=_to_str(video_stream.get("codec_name")),
                width=_to_int(video_stream.get("width")),
                height=_to_int(video_stream.get("height")),
                fps=_parse_fps(video_stream.get("avg_frame_rate")) or _parse_fps(video_stream.get("r_frame_rate")),
                pixel_format=_to_str(video_stream.get("pix_fmt")),
                bitrate=_to_int(video_stream.get("bit_rate")),
            ),
            audio=None if audio_stream is None else AudioStreamMetadata(
                codec=_to_str(audio_stream.get("codec_name")),
                bitrate=_to_int(audio_stream.get("bit_rate")),
                sample_rate=_to_int(audio_stream.get("sample_rate")),
                channels=_to_int(audio_stream.get("channels")),
            ),
        )

    @staticmethod
    def _reject_obviously_unsupported(filename: str) -> None:
        suffix = Path(filename).suffix.lower()
        if suffix and suffix not in SUPPORTED_VIDEO_EXTENSIONS:
            raise UnsupportedMediaError()


def _to_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _to_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 and math.isfinite(number) else None


def _parse_fps(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        result = float(value)
        return result if result > 0 and math.isfinite(result) else None
    if not isinstance(value, str) or not value:
        return None
    try:
        if "/" in value:
            numerator, denominator = value.split("/", maxsplit=1)
            result = int(numerator) / int(denominator)
        else:
            result = float(value)
    except (ValueError, ZeroDivisionError):
        return None
    return result if result > 0 and math.isfinite(result) else None
