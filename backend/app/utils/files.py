from pathlib import Path
from uuid import uuid4


def generate_storage_key(extension: str = "") -> str:
    """Create a server-owned object key; never derive paths from upload names."""
    safe_extension = extension if extension.startswith(".") and len(extension) <= 16 else ""
    return f"uploads/{uuid4().hex}{safe_extension.lower()}"


def original_filename_metadata(filename: str) -> str:
    """Retain a bounded display name only; it is not a filesystem path."""
    return Path(filename.replace("\\", "/")).name[:255]
