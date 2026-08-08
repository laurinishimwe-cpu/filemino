import shutil
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from app.storage.base import FileStorage, SignedDownload, SignedUpload, StoredObject


class LocalStorage(FileStorage):
    """Filesystem storage for development; production uses R2 signed URLs."""

    def __init__(self, root: Path, api_prefix: str = "/api/v1") -> None:
        self._root = root.resolve()
        self._api_prefix = api_prefix.rstrip("/")

    def create_upload_url(self, object_key: str, upload_id: UUID, expires_at: datetime, content_type: str | None) -> SignedUpload:
        self._safe_path(object_key)
        return SignedUpload(f"{self._api_prefix}/uploads/{upload_id}/content", expires_at)

    def create_download_url(self, object_key: str, expires_at: datetime) -> SignedDownload:
        self._safe_path(object_key)
        return SignedDownload(f"{self._api_prefix}/downloads/{object_key}", expires_at)

    def object_info(self, object_key: str) -> StoredObject | None:
        path = self._safe_path(object_key)
        if not path.is_file():
            return None
        return StoredObject(object_key, path.stat().st_size)

    def put(self, source: Path, object_key: str) -> str:
        destination = self._safe_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return object_key

    def put_stream(self, stream: BinaryIO, object_key: str, max_bytes: int) -> int:
        destination = self._safe_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        size_bytes = 0
        try:
            with destination.open("xb") as target:
                while chunk := stream.read(64 * 1024):
                    size_bytes += len(chunk)
                    if size_bytes > max_bytes:
                        raise ValueError("Storage size limit exceeded.")
                    target.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return size_bytes

    def download_to(self, object_key: str, destination: Path) -> Path:
        source = self._safe_path(object_key)
        if not source.is_file():
            raise FileNotFoundError(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return destination

    def delete(self, object_key: str) -> None:
        self._safe_path(object_key).unlink(missing_ok=True)

    def _safe_path(self, object_key: str) -> Path:
        candidate = (self._root / object_key).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError("Invalid storage object key.")
        return candidate
