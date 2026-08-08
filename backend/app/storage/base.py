from abc import ABC, abstractmethod
from pathlib import Path


class FileStorage(ABC):
    @abstractmethod
    def put(self, source: Path, object_key: str) -> str:
        """Store a server-generated object key and return its storage reference."""

    @abstractmethod
    def get_path(self, object_key: str) -> Path:
        """Resolve a trusted object key to a local path when supported."""
