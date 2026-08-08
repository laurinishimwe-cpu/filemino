from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.models.video import CompressionMode, ResolutionOption

ProgressCallback = Callable[[int], None]
CancellationCheck = Callable[[], bool]


class EncodingError(Exception):
    error_code = "encoding_failed"


class EncodingCancelled(EncodingError):
    error_code = "cancelled"


class EncodingTimeoutError(EncodingError):
    error_code = "encoding_timeout"


class TargetSizeError(EncodingError):
    error_code = "invalid_target_size"


@dataclass(frozen=True, slots=True)
class EncodingRequest:
    source: Path
    destination: Path
    duration_seconds: float
    mode: CompressionMode
    resolution: ResolutionOption
    target_size_bytes: int | None = None


class VideoEncoder(ABC):
    @abstractmethod
    def compress(
        self,
        request: EncodingRequest,
        on_progress: ProgressCallback,
        is_cancelled: CancellationCheck,
    ) -> None:
        """Encode with trusted paths and fixed options only."""
