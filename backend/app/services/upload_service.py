from datetime import timedelta
from typing import BinaryIO
from uuid import UUID

from app.core.exceptions import FileTooLargeError, NotFoundError, ValidationError
from app.models.job import utc_now
from app.models.upload import Upload
from app.repositories.upload_repository import UploadRepository
from app.services.job_service import JobService
from app.services.video_probe_service import VideoProbeService
from app.storage.base import FileStorage, SignedUpload
from app.utils.files import generate_storage_key, original_filename_metadata
from app.services.guest_policy_service import GuestPolicyService


class UploadService:
    def __init__(self, repository: UploadRepository, storage: FileStorage, probe_service: VideoProbeService, retention_seconds: int, signed_url_expiry_seconds: int, max_upload_size_bytes: int, policy: GuestPolicyService | None = None) -> None:
        self._repository = repository; self._storage = storage; self._probe_service = probe_service
        self._retention_seconds = retention_seconds; self._signed_url_expiry_seconds = signed_url_expiry_seconds; self._max_upload_size_bytes = max_upload_size_bytes
        self._policy=policy

    def initialize(self, filename: str, content_type: str | None, client_hash: str | None = None) -> tuple[Upload, SignedUpload]:
        now = utc_now(); upload = Upload(storage_key=generate_storage_key(".mp4"), original_filename=original_filename_metadata(filename), content_type=content_type, client_hash=client_hash, created_at=now, expires_at=now + timedelta(seconds=self._retention_seconds))
        signed = self._storage.create_upload_url(upload.storage_key, upload.id, now + timedelta(seconds=self._signed_url_expiry_seconds), content_type)
        self._repository.create(upload, self._retention_seconds)
        return upload, signed

    def complete_video_upload(self, upload_id: UUID, job_service: JobService):
        upload = self._get(upload_id)
        info = self._storage.object_info(upload.storage_key)
        if info is None: raise ValidationError("Upload has not completed.")
        if info.size_bytes <= 0: raise ValidationError("Upload is empty.")
        if self._policy:self._policy.validate_size(info.size_bytes)
        elif info.size_bytes > self._max_upload_size_bytes: raise FileTooLargeError()
        metadata = self._probe_service.probe_storage(upload.storage_key, upload.original_filename, info.size_bytes)
        complexity=self._policy.validate_video(metadata).value if self._policy else None
        job = job_service.create_video_job(upload.original_filename, compression_mode=None, target_size_bytes=None, resolution=None, input_metadata={"size_bytes":info.size_bytes,"duration_seconds": metadata.duration_seconds, "width": metadata.video.width, "height": metadata.video.height,"complexity": complexity}, input_storage_key=upload.storage_key,client_hash=upload.client_hash, route_by_metadata=True)
        self._repository.delete(upload_id)
        return job

    def store_local_content(self, upload_id: UUID, stream: BinaryIO) -> int:
        upload = self._get(upload_id)
        return self._storage.put_stream(stream, upload.storage_key, self._max_upload_size_bytes)

    def _get(self, upload_id: UUID) -> Upload:
        upload = self._repository.get(upload_id)
        if upload is None: raise NotFoundError()
        return upload
