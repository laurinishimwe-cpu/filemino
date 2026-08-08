from dataclasses import asdict
from datetime import timedelta
from typing import BinaryIO
from uuid import UUID

from app.core.exceptions import FileTooLargeError, IncompatibleImageOutputError, InvalidTargetSizeError, NotFoundError, UnsupportedImageConversionError, UnsupportedImageFormatError, ValidationError
from app.models.image import ImageCompressionMode, ImageConversionOutputFormat, ImageOutputFormat, ImageResizeOption, image_format_capability
from app.models.job import utc_now
from app.models.video import CompressionMode, ResolutionOption
from app.models.upload import Upload
from app.repositories.upload_repository import UploadRepository
from app.services.job_service import JobService
from app.services.video_probe_service import VideoProbeService
from app.services.image_probe_service import ImageProbeService
from app.storage.base import FileStorage, SignedUpload
from app.utils.files import generate_storage_key, original_filename_metadata
from app.services.guest_policy_service import GuestPolicyService


class UploadService:
    def __init__(self, repository: UploadRepository, storage: FileStorage, probe_service: VideoProbeService, retention_seconds: int, signed_url_expiry_seconds: int, max_upload_size_bytes: int, policy: GuestPolicyService | None = None, image_probe_service: ImageProbeService | None = None, image_min_target_size_bytes: int = 1_024, image_max_target_size_bytes: int = 50 * 1024 * 1024, image_queue_name: str = "image-cpu", image_max_upload_size_bytes: int | None = None) -> None:
        self._repository = repository; self._storage = storage; self._probe_service = probe_service
        self._retention_seconds = retention_seconds; self._signed_url_expiry_seconds = signed_url_expiry_seconds; self._max_upload_size_bytes = max_upload_size_bytes
        self._policy=policy
        self._image_probe_service = image_probe_service
        self._image_min_target_size_bytes = image_min_target_size_bytes
        self._image_max_target_size_bytes = image_max_target_size_bytes
        self._image_queue_name = image_queue_name
        self._image_max_upload_size_bytes = max_upload_size_bytes if image_max_upload_size_bytes is None else image_max_upload_size_bytes

    def initialize(self, filename: str, content_type: str | None, client_hash: str | None = None) -> tuple[Upload, SignedUpload]:
        now = utc_now(); upload = Upload(storage_key=generate_storage_key(".mp4"), original_filename=original_filename_metadata(filename), content_type=content_type, client_hash=client_hash, created_at=now, expires_at=now + timedelta(seconds=self._retention_seconds))
        signed = self._storage.create_upload_url(upload.storage_key, upload.id, now + timedelta(seconds=self._signed_url_expiry_seconds), content_type)
        self._repository.create(upload, self._retention_seconds)
        return upload, signed

    def complete_video_upload(
        self,
        upload_id: UUID,
        job_service: JobService,
        compression_mode: CompressionMode | None = None,
        target_size_bytes: int | None = None,
        resolution: ResolutionOption | None = None,
    ):
        upload = self._get(upload_id)
        info = self._storage.object_info(upload.storage_key)
        if info is None: raise ValidationError("Upload has not completed.")
        if info.size_bytes <= 0: raise ValidationError("Upload is empty.")
        if self._policy:self._policy.validate_size(info.size_bytes)
        elif info.size_bytes > self._max_upload_size_bytes: raise FileTooLargeError()
        metadata = self._probe_service.probe_storage(upload.storage_key, upload.original_filename, info.size_bytes)
        complexity=self._policy.validate_video(metadata).value if self._policy else None
        job = job_service.create_video_job(upload.original_filename, compression_mode=compression_mode, target_size_bytes=target_size_bytes, resolution=resolution, input_metadata={"size_bytes":info.size_bytes,"duration_seconds": metadata.duration_seconds, "width": metadata.video.width, "height": metadata.video.height,"complexity": complexity}, input_storage_key=upload.storage_key,client_hash=upload.client_hash, route_by_metadata=True)
        self._repository.delete(upload_id)
        return job

    def complete_image_upload(
        self,
        upload_id: UUID,
        job_service: JobService,
        compression_mode: ImageCompressionMode,
        target_size_bytes: int | None,
        output_format: ImageOutputFormat,
        resize: ImageResizeOption,
        quality_percent: int | None = None,
        resize_percent: int | None = None,
        custom_width: int | None = None,
        custom_height: int | None = None,
        lock_aspect_ratio: bool = True,
        allow_resize_for_target: bool = True,
    ):
        if self._image_probe_service is None:
            raise ValidationError("Image upload handling is unavailable.")
        if target_size_bytes is not None and not self._image_min_target_size_bytes <= target_size_bytes <= self._image_max_target_size_bytes:
            raise InvalidTargetSizeError()
        if compression_mode is ImageCompressionMode.TARGET_SIZE and target_size_bytes is None:
            raise InvalidTargetSizeError()
        if quality_percent is not None and not 1 <= quality_percent <= 100:
            raise ValidationError("Image quality must be between 1 and 100.")
        if resize_percent is not None and not 1 <= resize_percent <= 100:
            raise ValidationError("Image resize percentage must be between 1 and 100.")
        if custom_width is not None and custom_width < 1 or custom_height is not None and custom_height < 1:
            raise ValidationError("Custom image dimensions must be positive.")
        upload = self._get(upload_id)
        info = self._storage.object_info(upload.storage_key)
        if info is None: raise ValidationError("Upload has not completed.")
        if info.size_bytes <= 0: raise ValidationError("Upload is empty.")
        if info.size_bytes > self._image_max_upload_size_bytes: raise FileTooLargeError()
        metadata = self._image_probe_service.probe_storage(upload.storage_key, upload.original_filename, info.size_bytes)
        if output_format is ImageOutputFormat.JPEG and metadata.has_alpha:
            raise IncompatibleImageOutputError()
        job = job_service.create_image_job(
            upload.original_filename,
            compression_mode,
            target_size_bytes,
            output_format,
            resize,
            quality_percent,
            resize_percent,
            custom_width,
            custom_height,
            lock_aspect_ratio,
            allow_resize_for_target,
            input_metadata=asdict(metadata),
            input_storage_key=upload.storage_key,
            client_hash=upload.client_hash,
            queue_name=self._image_queue_name,
        )
        self._repository.delete(upload_id)
        return job

    def complete_image_conversion_upload(
        self,
        upload_id: UUID,
        job_service: JobService,
        output_format: ImageConversionOutputFormat,
        quality_percent: int | None = None,
        background_color: str | None = None,
    ):
        if self._image_probe_service is None:
            raise ValidationError("Image upload handling is unavailable.")
        upload = self._get(upload_id)
        info = self._storage.object_info(upload.storage_key)
        if info is None or info.size_bytes <= 0:
            raise ValidationError("Upload has not completed.")
        if info.size_bytes > self._image_max_upload_size_bytes:
            raise FileTooLargeError()
        metadata = self._image_probe_service.probe_storage(upload.storage_key, upload.original_filename, info.size_bytes)
        capability = image_format_capability(metadata.format)
        if capability is None:
            raise UnsupportedImageFormatError()
        if output_format not in capability.conversion_targets:
            raise UnsupportedImageConversionError()
        if output_format is ImageConversionOutputFormat.JPEG and metadata.has_alpha and background_color is None:
            raise IncompatibleImageOutputError()
        job = job_service.create_image_conversion_job(
            upload.original_filename,
            output_format,
            quality_percent,
            background_color,
            input_metadata=asdict(metadata),
            input_storage_key=upload.storage_key,
            client_hash=upload.client_hash,
            queue_name=self._image_queue_name,
        )
        self._repository.delete(upload_id)
        return job

    def store_local_content(self, upload_id: UUID, stream: BinaryIO) -> int:
        upload = self._get(upload_id)
        return self._storage.put_stream(stream, upload.storage_key, self._max_upload_size_bytes)

    def _get(self, upload_id: UUID) -> Upload:
        upload = self._repository.get(upload_id)
        if upload is None: raise NotFoundError()
        return upload
