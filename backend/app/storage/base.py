from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size_bytes: int
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class SignedUpload:
    url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SignedDownload:
    url: str
    expires_at: datetime


class FileStorage(ABC):
    @abstractmethod
    def create_upload_url(self, object_key: str, upload_id: UUID, expires_at: datetime, content_type: str | None) -> SignedUpload:
        """Authorize a server-generated key for one temporary browser upload."""

    @abstractmethod
    def create_download_url(self, object_key: str, expires_at: datetime) -> SignedDownload:
        """Authorize a temporary private download."""

    @abstractmethod
    def object_info(self, object_key: str) -> StoredObject | None:
        """Return metadata for a trusted key without exposing provider internals."""

    @abstractmethod
    def put_stream(self, stream: BinaryIO, object_key: str, max_bytes: int) -> int:
        """Development fallback for uploads passing through the API."""

    @abstractmethod
    def put(self, source: Path, object_key: str) -> str:
        """Store a server-generated object key and return its storage reference."""

    @abstractmethod
    def download_to(self, object_key: str, destination: Path) -> Path:
        """Materialize a trusted object into worker scratch storage."""

    @abstractmethod
    def delete(self, object_key: str) -> None:
        """Remove an object during retention cleanup."""
