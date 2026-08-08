from abc import ABC, abstractmethod
from pathlib import Path

from app.models.video import CompressionMode, ResolutionOption


class VideoEncoder(ABC):
    @abstractmethod
    def compress(
        self,
        source: Path,
        destination: Path,
        mode: CompressionMode,
        resolution: ResolutionOption,
    ) -> None:
        """Compress a video without constructing shell commands from user input."""
