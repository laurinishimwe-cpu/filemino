from dataclasses import dataclass
from enum import StrEnum


class CompressionMode(StrEnum):
    BEST_QUALITY = "best_quality"
    BALANCED = "balanced"
    SMALLEST_SIZE = "smallest_size"


class ResolutionOption(StrEnum):
    ORIGINAL = "original"
    HD_1080 = "1080"
    HD_720 = "720"
    SD_480 = "480"


@dataclass(frozen=True, slots=True)
class VideoStreamMetadata:
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    pixel_format: str | None = None
    bitrate: int | None = None


@dataclass(frozen=True, slots=True)
class AudioStreamMetadata:
    codec: str | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    filename: str
    size_bytes: int
    duration_seconds: float | None
    container: str | None
    bitrate: int | None
    video: VideoStreamMetadata
    audio: AudioStreamMetadata | None = None
