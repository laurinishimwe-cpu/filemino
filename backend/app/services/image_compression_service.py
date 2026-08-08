import logging
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from app.encoders.image.base import ImageEncoder, ImageEncoderConfig, ImageEncodingRequest
from app.models.image import (
    ImageCompressionMode,
    ImageMetadata,
    ImageOutputFormat,
    ImageResizeOption,
    resolve_image_output_format,
)
from app.models.job import Job
from app.services.image_probe_service import ImageProbeService
from app.storage.base import FileStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImageCompressionOutcome:
    output_storage_key: str
    output_metadata: dict
    size_reduction_percent: int | None


class ImageCompressionService:
    """Coordinates reusable storage, image probing, and the image encoder abstraction."""

    def __init__(
        self,
        encoder: ImageEncoder,
        storage: FileStorage,
        probe_service: ImageProbeService,
        temp_directory: Path,
        encoder_config: ImageEncoderConfig,
    ) -> None:
        self._encoder = encoder
        self._storage = storage
        self._probe_service = probe_service
        self._temp_directory = temp_directory
        self._encoder_config = encoder_config

    def probe_input(self, job: Job) -> ImageMetadata:
        with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
            source = self._storage.download_to(job.input_storage_key, Path(workspace) / "input")
            return self._probe_service.probe(source, filename=job.original_filename)

    def compress(
        self,
        job: Job,
        input_metadata: ImageMetadata,
        on_progress: Callable[[int], None] | None = None,
    ) -> ImageCompressionOutcome:
        mode = job.compression_mode
        if not isinstance(mode, ImageCompressionMode):
            raise ValueError("Image jobs require image compression modes.")
        output_format = job.image_output_format or ImageOutputFormat.ORIGINAL
        resize = job.image_resize or ImageResizeOption.KEEP_ORIGINAL
        actual_output_format = resolve_image_output_format(
            output_format,
            input_metadata.format,
            input_metadata.has_alpha,
            mode,
        )
        output_extension = _output_extension(actual_output_format)
        output_key = f"outputs/{uuid4().hex}{output_extension}"
        self._temp_directory.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
                source_path = self._storage.download_to(job.input_storage_key, Path(workspace) / "input")
                output_path = Path(workspace) / f"compressed{output_extension}"
                encoded = self._encoder.compress(
                    ImageEncodingRequest(
                        source=source_path,
                        destination=output_path,
                        mode=mode,
                        target_size_bytes=job.target_size_bytes,
                        output_format=output_format,
                        resize=resize,
                        config=self._encoder_config,
                        quality_percent=job.image_quality_percent,
                        resize_percent=job.image_resize_percent,
                        custom_width=job.image_custom_width,
                        custom_height=job.image_custom_height,
                        lock_aspect_ratio=job.image_lock_aspect_ratio,
                        allow_resize_for_target=job.image_allow_resize_for_target,
                        on_progress=on_progress,
                    )
                )
                self._storage.put(output_path, output_key)

            with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
                output_path = self._storage.download_to(output_key, Path(workspace) / f"output{output_extension}")
                output_metadata = self._probe_service.probe(output_path, filename=f"compressed{output_extension}")
        except Exception:
            self.discard_output(output_key)
            raise
        metadata = asdict(output_metadata)
        metadata.update(
            target_size_bytes=job.target_size_bytes,
            target_achieved=encoded.target_achieved,
            resized_for_target=encoded.resized_for_target,
            output_format=encoded.format,
            quality_percent=job.image_quality_percent,
            allow_resize_for_target=job.image_allow_resize_for_target,
        )
        return ImageCompressionOutcome(output_key, metadata, _size_reduction_percent(input_metadata.size_bytes, output_metadata.size_bytes))

    def discard_output(self, output_storage_key: str) -> None:
        """Best-effort removal for outputs that never become a completed job."""
        try:
            self._storage.delete(output_storage_key)
        except Exception:
            logger.warning("Could not remove incomplete image output", exc_info=True)


def _output_extension(image_format: str) -> str:
    return {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image_format]


def _size_reduction_percent(input_size: int, output_size: int) -> int | None:
    if input_size <= 0:
        return None
    return max(0, round((1 - output_size / input_size) * 100))
