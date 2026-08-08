from pydantic import BaseModel, Field

from app.models.video import CompressionMode, ResolutionOption


class VideoCompressionOptions(BaseModel):
    compression_mode: CompressionMode = CompressionMode.BALANCED
    resolution: ResolutionOption = ResolutionOption.ORIGINAL
    target_size_mb: int | None = Field(default=None, gt=0)


class VideoMetadataResponse(BaseModel):
    duration_seconds: float = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    mime_type: str | None = None
