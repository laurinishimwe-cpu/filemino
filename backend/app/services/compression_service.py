import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from app.encoders.base import CancellationCheck, EncodingRequest, ProgressCallback, VideoEncoder
from app.models.job import Job
from app.models.video import VideoMetadata
from app.services.video_probe_service import VideoProbeService
from app.storage.base import FileStorage


@dataclass(frozen=True, slots=True)
class CompressionOutcome:
    output_storage_key: str
    output_metadata: dict
    size_reduction_percent: int | None


class CompressionService:
    """Coordinates storage, probe, and an interchangeable video encoder."""

    def __init__(
        self,
        encoder: VideoEncoder,
        storage: FileStorage,
        probe_service: VideoProbeService,
        temp_directory: Path,
    ) -> None:
        self._encoder = encoder
        self._storage = storage
        self._probe_service = probe_service
        self._temp_directory = temp_directory

    def probe_input(self, job: Job) -> VideoMetadata:
        with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
            source = self._storage.download_to(job.input_storage_key, Path(workspace) / "input")
            return self._probe_service.probe(source, filename=job.original_filename)

    def compress(
        self,
        job: Job,
        input_metadata: VideoMetadata,
        on_progress: ProgressCallback,
        is_cancelled: CancellationCheck,
    ) -> CompressionOutcome:
        output_key = f"outputs/{uuid4().hex}.mp4"
        self._temp_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
            source_path = self._storage.download_to(job.input_storage_key, Path(workspace) / "input")
            output_path = Path(workspace) / "compressed.mp4"
            self._encoder.compress(
                EncodingRequest(
                    source=source_path,
                    destination=output_path,
                    duration_seconds=input_metadata.duration_seconds or 0,
                    mode=job.compression_mode,
                    resolution=job.resolution,
                    target_size_bytes=job.target_size_bytes,
                ),
                on_progress,
                is_cancelled,
            )
            self._storage.put(output_path, output_key)

        with tempfile.TemporaryDirectory(dir=self._temp_directory) as workspace:
            output_path = self._storage.download_to(output_key, Path(workspace) / "output.mp4")
            output_metadata = self._probe_service.probe(output_path, filename="compressed.mp4")
        reduction = _size_reduction_percent(input_metadata.size_bytes, output_metadata.size_bytes)
        return CompressionOutcome(output_key, asdict(output_metadata), reduction)


def _size_reduction_percent(input_size: int, output_size: int) -> int | None:
    if input_size <= 0:
        return None
    return max(0, round((1 - output_size / input_size) * 100))
