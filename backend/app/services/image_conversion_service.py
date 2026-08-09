from __future__ import annotations

import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from app.encoders.image.conversion import PillowImageConverter
from app.models.image import ImageConversionOutputFormat, ImageMetadata
from app.core.exceptions import IncompatibleImageOutputError, UnsupportedImageConversionError, UnsupportedImageFormatError
from app.models.image import image_format_capability
from app.models.job import Job
from app.services.image_probe_service import ImageProbeService
from app.storage.base import FileStorage


@dataclass(frozen=True, slots=True)
class ImageConversionOutcome:
    output_storage_key: str
    output_metadata: dict


class ImageConversionService:
    def __init__(self, converter: PillowImageConverter, storage: FileStorage, probe_service: ImageProbeService, temp_directory: Path) -> None:
        self._converter = converter
        self._storage = storage
        self._probe_service = probe_service
        self._temp_directory = temp_directory

    def probe_input(self, job: Job) -> ImageMetadata:
        with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
            source = self._storage.download_to(job.input_storage_key, Path(workspace) / "input")
            return self._probe_service.probe(source, filename=job.original_filename)

    def convert(self, job: Job, input_metadata: ImageMetadata) -> ImageConversionOutcome:
        output_format = job.image_conversion_output_format
        assert output_format is not None
        capability = image_format_capability(input_metadata.format)
        if capability is None:
            raise UnsupportedImageFormatError()
        if output_format not in capability.conversion_targets:
            raise UnsupportedImageConversionError()
        if input_metadata.has_alpha and output_format is ImageConversionOutputFormat.JPEG and job.image_conversion_background_color is None:
            raise IncompatibleImageOutputError()
        extension = {ImageConversionOutputFormat.PNG: ".png", ImageConversionOutputFormat.JPEG: ".jpg", ImageConversionOutputFormat.WEBP: ".webp", ImageConversionOutputFormat.ICO: ".ico"}[output_format]
        output_key = f"outputs/{uuid4().hex}{extension}"
        try:
            with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
                source = self._storage.download_to(job.input_storage_key, Path(workspace) / "input")
                destination = Path(workspace) / f"converted{extension}"
                converted = self._converter.convert(source, destination, output_format, job.image_conversion_quality_percent, job.image_conversion_background_color, job.image_conversion_ico_sizes, job.image_conversion_ico_source_size)
                self._storage.put(destination, output_key)
            with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
                result = self._storage.download_to(output_key, Path(workspace) / f"result{extension}")
                output_metadata = self._probe_service.probe(result, filename=f"converted{extension}")
        except Exception:
            self._storage.delete(output_key)
            raise
        metadata = asdict(output_metadata)
        metadata.update(source_format=input_metadata.format, output_format=output_metadata.format, original_width=input_metadata.width, original_height=input_metadata.height, original_size_bytes=input_metadata.size_bytes, output_size_bytes=output_metadata.size_bytes, alpha_preserved=converted.alpha_preserved, background_flattened=converted.background_flattened, background_color=job.image_conversion_background_color if converted.background_flattened else None, quality_percent=job.image_conversion_quality_percent, source_icon_size=converted.source_icon_size, selected_source_icon_size=converted.source_icon_size, available_source_icon_sizes=input_metadata.available_icon_sizes, generated_icon_sizes=converted.generated_icon_sizes)
        return ImageConversionOutcome(output_key, metadata)

    def discard_output(self, output_storage_key: str) -> None:
        self._storage.delete(output_storage_key)
