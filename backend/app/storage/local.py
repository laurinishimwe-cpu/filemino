import shutil
from pathlib import Path

from app.storage.base import FileStorage


class LocalStorage(FileStorage):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def put(self, source: Path, object_key: str) -> str:
        destination = self._safe_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return object_key

    def get_path(self, object_key: str) -> Path:
        return self._safe_path(object_key)

    def _safe_path(self, object_key: str) -> Path:
        candidate = (self._root / object_key).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError("Invalid storage object key.")
        return candidate
