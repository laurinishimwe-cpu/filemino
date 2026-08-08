import tempfile
import warnings
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import (
    FileTooLargeError,
    ImageDimensionsExceededError,
    InvalidImageError,
    UnsupportedAnimatedImageError,
    UnsupportedMediaError,
)
from app.models.image import ImageMetadata
from app.storage.base import FileStorage
from app.utils.files import generate_storage_key, original_filename_metadata

# This is the common static raster surface used by both compression and
# conversion.  Each use case applies its own narrower output policy.
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "ICO", "BMP", "TIFF"}


class ImageProbeService:
    """Decode and normalize untrusted image metadata without trusting file names."""

    def __init__(
        self,
        storage: FileStorage,
        max_upload_size_bytes: int,
        max_pixels: int,
        max_width: int,
        max_height: int,
        scratch_directory: Path | None = None,
    ) -> None:
        self._storage = storage
        self._max_upload_size_bytes = max_upload_size_bytes
        self._max_pixels = max_pixels
        self._max_width = max_width
        self._max_height = max_height
        self._scratch_directory = scratch_directory

    def probe_upload(self, stream: BinaryIO, original_filename: str | None) -> ImageMetadata:
        object_key = generate_storage_key(".image")
        try:
            try:
                size_bytes = self._storage.put_stream(stream, object_key, self._max_upload_size_bytes)
            except ValueError as exc:
                raise FileTooLargeError() from exc
            if size_bytes <= 0:
                raise InvalidImageError()
            return self.probe_storage(object_key, original_filename or "upload", size_bytes)
        finally:
            self._storage.delete(object_key)

    def probe_storage(self, object_key: str, filename: str, size_bytes: int) -> ImageMetadata:
        with tempfile.TemporaryDirectory(dir=self._scratch_directory) as workspace:
            source = self._storage.download_to(object_key, Path(workspace) / "probe-input")
            return self.probe(source, filename=filename, size_bytes=size_bytes)

    def probe(self, source: Path, filename: str | None = None, size_bytes: int | None = None) -> ImageMetadata:
        if not source.is_file():
            raise InvalidImageError()
        actual_size = source.stat().st_size if size_bytes is None else size_bytes
        if actual_size <= 0:
            raise InvalidImageError()
        if actual_size > self._max_upload_size_bytes:
            raise FileTooLargeError()

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(source) as image:
                    image.load()
                    image_format = (image.format or "").upper()
                    animated = bool(getattr(image, "is_animated", False))
                    frame_count = int(getattr(image, "n_frames", 1))
                    if animated or frame_count > 1:
                        raise UnsupportedAnimatedImageError()
                    if image_format not in SUPPORTED_IMAGE_FORMATS:
                        raise UnsupportedMediaError()
                    normalized = ImageOps.exif_transpose(image)
                    width, height = normalized.size
                    self._validate_dimensions(width, height)
                    return ImageMetadata(
                        filename=original_filename_metadata(filename or source.name),
                        size_bytes=actual_size,
                        format=image_format,
                        width=width,
                        height=height,
                        mode=normalized.mode,
                        has_alpha=_has_alpha(normalized),
                        animated=False,
                        frame_count=1,
                    )
        except (UnsupportedMediaError, UnsupportedAnimatedImageError, ImageDimensionsExceededError):
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidImageError() from exc

    def _validate_dimensions(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0 or width > self._max_width or height > self._max_height:
            raise ImageDimensionsExceededError()
        if width * height > self._max_pixels:
            raise ImageDimensionsExceededError()


def _has_alpha(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info
