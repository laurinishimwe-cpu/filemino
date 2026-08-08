from pathlib import Path
from uuid import UUID

from app.models.video import CompressionMode, ResolutionOption


class CompressionService:
    """Coordinates future storage, encoder, and queue implementations."""

    def request_compression(
        self,
        job_id: UUID,
        source: Path,
        mode: CompressionMode,
        resolution: ResolutionOption,
    ) -> None:
        raise NotImplementedError("Compression is dispatched to workers in a future stage.")
