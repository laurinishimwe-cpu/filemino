from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from math import sqrt
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import IncompatibleImageOutputError, InvalidImageError, InvalidTargetSizeError
from app.encoders.image.base import (
    EncodedImage,
    ImageEncoder,
    ImageEncoderConfig,
    ImageEncodingRequest,
    ImageTargetSizeUnreachable,
    TargetSizeFailureContext,
)
from app.models.image import ImageCompressionMode, ImageOutputFormat, ImageResizeOption, resolve_image_output_format

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _TargetCandidate:
    payload: bytes
    quality: int
    palette_colors: int | None
    width: int
    height: int


@dataclass(slots=True)
class _TargetSearchState:
    target_bytes: int
    smallest: _TargetCandidate | None = None
    completed_attempts: int = 0
    total_attempts: int = 1
    last_progress: int = 20

    def observe(self, candidate: _TargetCandidate, request: ImageEncodingRequest) -> None:
        self.completed_attempts += 1
        if self.smallest is None or len(candidate.payload) < len(self.smallest.payload):
            self.smallest = candidate
        logger.debug(
            "image_target_candidate",
            extra={
                "event": "image_target_candidate",
                "target_bytes": self.target_bytes,
                "candidate_bytes": len(candidate.payload),
                "width": candidate.width,
                "height": candidate.height,
                "quality": candidate.quality,
                "palette_colors": candidate.palette_colors,
            },
        )
        self._report_progress(min(90, 30 + round(40 * self.completed_attempts / self.total_attempts)), request)

    def begin_resize_refinement(self, resize_attempt: int, maximum_resizes: int, request: ImageEncodingRequest) -> None:
        progress = 70 + round(20 * resize_attempt / max(1, maximum_resizes))
        self._report_progress(progress, request)

    def _report_progress(self, progress: int, request: ImageEncodingRequest) -> None:
        self.last_progress = max(self.last_progress, progress)
        if request.on_progress is not None:
            request.on_progress(self.last_progress)


class PillowImageEncoder(ImageEncoder):
    """Pillow encoder with semantic quality and bounded target-size searching."""

    def probe(self, source: Path) -> None:
        try:
            with Image.open(source) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidImageError() from exc

    def compress(self, request: ImageEncodingRequest) -> EncodedImage:
        image, source_format = self._load(request.source)
        output_format = resolve_image_output_format(request.output_format, source_format, _has_alpha(image), request.mode)
        if output_format == "JPEG" and _has_alpha(image):
            raise IncompatibleImageOutputError()

        image = _apply_requested_resize(image, request)
        if request.mode is ImageCompressionMode.TARGET_SIZE and request.target_size_bytes is None:
            raise InvalidTargetSizeError()
        if request.target_size_bytes is None:
            quality = _quality_for_mode(request)
            payload = self._encode(image, output_format, quality, request.config)
            target_achieved: bool | None = None
            resized_for_target = False
        else:
            payload, image, resized_for_target = self._encode_for_target(image, output_format, request)
            target_achieved = len(payload) <= request.target_size_bytes

        request.destination.parent.mkdir(parents=True, exist_ok=True)
        request.destination.write_bytes(payload)
        return EncodedImage(output_format, image.width, image.height, _has_alpha(image), target_achieved, resized_for_target)

    def _load(self, source: Path) -> tuple[Image.Image, str]:
        try:
            with Image.open(source) as opened:
                source_format = (opened.format or "").upper()
                opened.load()
                return ImageOps.exif_transpose(opened).copy(), source_format
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidImageError() from exc

    def _encode_for_target(self, image: Image.Image, output_format: str, request: ImageEncodingRequest) -> tuple[bytes, Image.Image, bool]:
        target = request.target_size_bytes
        assert target is not None
        if not request.config.min_target_size_bytes <= target <= request.config.max_target_size_bytes:
            raise InvalidTargetSizeError()

        maximum_resizes = request.config.target_resize_max_attempts if request.allow_resize_for_target else 0
        attempts_per_dimension = _target_attempt_budget(output_format, request.config)
        state = _TargetSearchState(target, total_attempts=(maximum_resizes + 1) * attempts_per_dimension)
        working = image
        logger.debug(
            "image_target_search_started",
            extra={
                "event": "image_target_search_started",
                "target_bytes": target,
                "width": image.width,
                "height": image.height,
                "output_format": output_format,
                "quality_floor_explicit": request.quality_percent is not None,
                "resize_allowed": request.allow_resize_for_target,
            },
        )
        for resize_attempt in range(maximum_resizes + 1):
            candidate = self._best_payload_for_target(working, output_format, request, state)
            if candidate is not None:
                return candidate.payload, working, resize_attempt > 0
            if resize_attempt == maximum_resizes:
                break
            smallest_size = len(state.smallest.payload) if state.smallest is not None else None
            next_size = _next_target_size(working.size, smallest_size, target, request.config)
            if next_size is None:
                break
            logger.debug(
                "image_target_resize_attempt",
                extra={
                    "event": "image_target_resize_attempt",
                    "target_bytes": target,
                    "from_width": working.width,
                    "from_height": working.height,
                    "to_width": next_size[0],
                    "to_height": next_size[1],
                    "smallest_candidate_bytes": smallest_size,
                },
            )
            state.begin_resize_refinement(resize_attempt + 1, maximum_resizes, request)
            working = working.resize(next_size, Image.Resampling.LANCZOS)

        smallest = state.smallest
        assert smallest is not None
        logger.debug(
            "image_target_search_exhausted",
            extra={
                "event": "image_target_search_exhausted",
                "target_bytes": target,
                "smallest_candidate_bytes": len(smallest.payload),
                "smallest_width": smallest.width,
                "smallest_height": smallest.height,
                "output_format": output_format,
            },
        )
        raise ImageTargetSizeUnreachable(
            TargetSizeFailureContext(
                requested_target_bytes=target,
                smallest_achieved_bytes=len(smallest.payload),
                smallest_width=smallest.width,
                smallest_height=smallest.height,
                output_format=output_format,
                quality_floor_was_explicit=request.quality_percent is not None,
                resize_allowed=request.allow_resize_for_target,
            )
        )

    def _best_payload_for_target(self, image: Image.Image, output_format: str, request: ImageEncodingRequest, state: _TargetSearchState) -> _TargetCandidate | None:
        minimum_quality = request.quality_percent if request.quality_percent is not None else request.config.min_quality
        if not 1 <= minimum_quality <= request.config.max_quality:
            raise InvalidTargetSizeError()
        if output_format == "PNG":
            attempted_palettes: set[int | None] = set()
            for quality in _png_target_qualities(request.config.max_quality, minimum_quality, request.config.target_search_max_attempts):
                palette_colors = _png_palette_colors_for_quality(quality, request.config)
                if palette_colors in attempted_palettes:
                    continue
                attempted_palettes.add(palette_colors)
                payload = self._encode(image, output_format, quality, request.config)
                candidate = _TargetCandidate(payload, quality, palette_colors, image.width, image.height)
                state.observe(candidate, request)
                if len(payload) <= state.target_bytes:
                    return candidate
            return None

        low, high, best = minimum_quality, request.config.max_quality, None
        while low <= high and state.completed_attempts < state.total_attempts:
            quality = (low + high) // 2
            payload = self._encode(image, output_format, quality, request.config)
            candidate = _TargetCandidate(payload, quality, None, image.width, image.height)
            state.observe(candidate, request)
            if len(payload) <= state.target_bytes:
                best = candidate
                low = quality + 1
            else:
                high = quality - 1
        return best

    @staticmethod
    def _encode(image: Image.Image, output_format: str, quality: int, config: ImageEncoderConfig) -> bytes:
        output = BytesIO()
        if output_format == "JPEG":
            image.convert("RGB").save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
        elif output_format == "WEBP":
            image.save(output, format="WEBP", quality=quality, method=6)
        elif output_format == "PNG":
            _png_image_for_quality(image, quality, config).save(output, format="PNG", optimize=True, compress_level=9)
        else:
            raise InvalidImageError()
        return output.getvalue()


def _quality_for_mode(request: ImageEncodingRequest) -> int:
    if request.mode is ImageCompressionMode.BEST_QUALITY:
        return request.config.best_quality_default
    if request.mode is ImageCompressionMode.BALANCED:
        return request.quality_percent or request.config.balanced_quality_default
    if request.mode is ImageCompressionMode.SMALLEST_SIZE:
        return request.quality_percent or request.config.smallest_quality_default
    return request.quality_percent or request.config.target_min_quality_default


def _apply_requested_resize(image: Image.Image, request: ImageEncodingRequest) -> Image.Image:
    option = request.resize
    if option is ImageResizeOption.KEEP_ORIGINAL:
        return image
    if option is ImageResizeOption.PERCENT_75:
        return _resize_to(image, round(image.width * 0.75), round(image.height * 0.75))
    if option is ImageResizeOption.PERCENT_50:
        return _resize_to(image, round(image.width * 0.5), round(image.height * 0.5))
    if option is ImageResizeOption.PERCENTAGE:
        if request.resize_percent is None or not 1 <= request.resize_percent <= 100:
            raise InvalidTargetSizeError()
        return _resize_to(image, round(image.width * request.resize_percent / 100), round(image.height * request.resize_percent / 100))
    if option is ImageResizeOption.CUSTOM:
        return _custom_resize(image, request.custom_width, request.custom_height, request.lock_aspect_ratio)
    raise InvalidImageError()


def _custom_resize(image: Image.Image, width: int | None, height: int | None, lock_aspect_ratio: bool) -> Image.Image:
    if width is None and height is None:
        raise InvalidTargetSizeError()
    if lock_aspect_ratio:
        if width is not None:
            height = max(1, round(image.height * width / image.width))
        else:
            assert height is not None
            width = max(1, round(image.width * height / image.height))
    if width is None or height is None:
        raise InvalidTargetSizeError()
    return _resize_to(image, width, height)


def _resize_to(image: Image.Image, width: int, height: int) -> Image.Image:
    if width < 1 or height < 1 or width > image.width or height > image.height:
        raise InvalidTargetSizeError()
    return image if (width, height) == image.size else image.resize((width, height), Image.Resampling.LANCZOS)


def _png_image_for_quality(image: Image.Image, quality: int, config: ImageEncoderConfig) -> Image.Image:
    if quality >= config.png_lossless_quality_threshold:
        return image
    colors = _png_palette_colors_for_quality(quality, config)
    if _has_alpha(image):
        return image.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
    return image.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT)


def _png_palette_colors_for_quality(quality: int, config: ImageEncoderConfig) -> int | None:
    if quality >= config.png_lossless_quality_threshold:
        return None
    for threshold, colors in zip(config.png_palette_quality_thresholds, config.png_palette_colors, strict=False):
        if quality >= threshold:
            return colors
    return config.png_palette_colors[-1]


def _png_target_qualities(maximum: int, minimum: int, attempts: int) -> list[int]:
    if attempts <= 1 or maximum == minimum:
        return [maximum]
    values = [round(maximum - index * (maximum - minimum) / (attempts - 1)) for index in range(attempts)]
    return list(dict.fromkeys([*values, minimum]))


def _next_target_size(size: tuple[int, int], smallest_bytes: int | None, target_bytes: int, config: ImageEncoderConfig) -> tuple[int, int] | None:
    if smallest_bytes is None or smallest_bytes <= 0:
        factor = config.target_resize_factor
    else:
        estimated_factor = sqrt(target_bytes / smallest_bytes) * 0.95
        factor = min(config.target_resize_factor, max(0.35, estimated_factor))
    return _scaled_size(size, factor, config.target_min_dimension)


def _target_attempt_budget(output_format: str, config: ImageEncoderConfig) -> int:
    if output_format == "PNG":
        return min(config.target_search_max_attempts, len(config.png_palette_colors) + 1)
    return config.target_search_max_attempts


def _scaled_size(size: tuple[int, int], factor: float, minimum: int) -> tuple[int, int] | None:
    width, height = size
    if width <= minimum and height <= minimum:
        return None
    next_width = max(minimum, int(width * factor))
    next_height = max(minimum, int(height * factor))
    return None if next_width >= width and next_height >= height else (next_width, next_height)


def _has_alpha(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info
