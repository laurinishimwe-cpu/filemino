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
class VideoMetadata:
    duration_seconds: float
    width: int
    height: int
    mime_type: str | None = None
