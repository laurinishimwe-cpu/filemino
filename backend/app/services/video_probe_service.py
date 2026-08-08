from pathlib import Path

from app.models.video import VideoMetadata


class VideoProbeService:
    def probe(self, source: Path) -> VideoMetadata:
        raise NotImplementedError("FFprobe integration will be added in a future stage.")
