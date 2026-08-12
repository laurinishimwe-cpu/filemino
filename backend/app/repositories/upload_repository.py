import json
from datetime import datetime
from typing import Protocol
from uuid import UUID

from redis import Redis

from app.models.upload import Upload


class UploadRepository(Protocol):
    def create(self, upload: Upload, ttl_seconds: int) -> Upload: ...
    def get(self, upload_id: UUID) -> Upload | None: ...
    def delete(self, upload_id: UUID) -> None: ...


class InMemoryUploadRepository:
    def __init__(self) -> None:
        self._uploads: dict[UUID, Upload] = {}
    def create(self, upload: Upload, ttl_seconds: int) -> Upload:
        self._uploads[upload.id] = upload
        return upload
    def get(self, upload_id: UUID) -> Upload | None:
        return self._uploads.get(upload_id)
    def delete(self, upload_id: UUID) -> None:
        self._uploads.pop(upload_id, None)


class RedisUploadRepository:
    key_prefix = "filemino:uploads"
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client
    def create(self, upload: Upload, ttl_seconds: int) -> Upload:
        self._redis.set(self._key(upload.id), json.dumps({"id": str(upload.id), "storage_key": upload.storage_key, "original_filename": upload.original_filename, "content_type": upload.content_type, "client_hash":upload.client_hash, "created_at": upload.created_at.isoformat() if upload.created_at else None, "expires_at": upload.expires_at.isoformat() if upload.expires_at else None}), ex=ttl_seconds)
        return upload
    def get(self, upload_id: UUID) -> Upload | None:
        raw = self._redis.get(self._key(upload_id))
        if raw is None: return None
        try:
            payload = json.loads(raw)
            return Upload(UUID(payload["id"]), payload["storage_key"], payload["original_filename"], payload.get("content_type"), payload.get("client_hash"), datetime.fromisoformat(payload["created_at"]), datetime.fromisoformat(payload["expires_at"]))
        except (KeyError, TypeError, ValueError):
            self.delete(upload_id); return None
    def delete(self, upload_id: UUID) -> None:
        self._redis.delete(self._key(upload_id))
    def _key(self, upload_id: UUID) -> str:
        return f"{self.key_prefix}:{upload_id}"
