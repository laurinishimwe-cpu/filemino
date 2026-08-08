from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.models.image import ImageCompressionMode, ImageOutputFormat, ImageResizeOption


class ImageEncodingError(Exception):
    error_code = "image_encoding_failed"


class ImageTargetSizeUnreachable(ImageEncodingError):
    error_code = "target_size_unreachable"

    def __init__(self, context: "TargetSizeFailureContext") -> None:
        self.context = context
        super().__init__("The image target size could not be reached.")


@dataclass(frozen=True, slots=True)
class TargetSizeFailureContext:
    requested_target_bytes: int
    smallest_achieved_bytes: int
    smallest_width: int
    smallest_height: int
    output_format: str
    quality_floor_was_explicit: bool
    resize_allowed: bool


@dataclass(frozen=True, slots=True)
class ImageEncoderConfig:
    min_target_size_bytes: int
    max_target_size_bytes: int
    min_quality: int
    max_quality: int
    target_search_max_attempts: int
    target_resize_max_attempts: int
    target_resize_factor: float
    target_min_dimension: int
    best_quality_default: int = 92
    balanced_quality_default: int = 80
    smallest_quality_default: int = 55
    target_min_quality_default: int = 45
    png_lossless_quality_threshold: int = 90
    png_palette_quality_thresholds: tuple[int, ...] = (75, 60, 40, 25)
    png_palette_colors: tuple[int, ...] = (256, 128, 64, 32, 16)


@dataclass(frozen=True, slots=True)
class ImageEncodingRequest:
    source: Path
    destination: Path
    mode: ImageCompressionMode
    target_size_bytes: int | None
    output_format: ImageOutputFormat
    resize: ImageResizeOption
    config: ImageEncoderConfig
    quality_percent: int | None = None
    resize_percent: int | None = None
    custom_width: int | None = None
    custom_height: int | None = None
    lock_aspect_ratio: bool = True
    allow_resize_for_target: bool = True
    on_progress: Callable[[int], None] | None = None


@dataclass(frozen=True, slots=True)
class EncodedImage:
    format: str
    width: int
    height: int
    has_alpha: bool
    target_achieved: bool | None
    resized_for_target: bool


class ImageEncoder(ABC):
    @abstractmethod
    def probe(self, source: Path) -> None:
        """Optionally validate an image with encoder-specific facilities."""

    @abstractmethod
    def compress(self, request: ImageEncodingRequest) -> EncodedImage:
        """Encode only from trusted local paths with centralized options."""
