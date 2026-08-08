from pydantic import BaseModel, ConfigDict, Field

from app.models.video import CompressionMode, ResolutionOption


class VideoCompressionOptions(BaseModel):
    compression_mode: CompressionMode = CompressionMode.BALANCED
    resolution: ResolutionOption = ResolutionOption.ORIGINAL
    target_size_mb: int | None = Field(default=None, gt=0)


class VideoStreamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codec: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, ge=0)
    pixel_format: str | None = None
    bitrate: int | None = Field(default=None, ge=0)


class AudioStreamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codec: str | None = None
    bitrate: int | None = Field(default=None, ge=0)
    sample_rate: int | None = Field(default=None, ge=0)
    channels: int | None = Field(default=None, ge=0)


class VideoMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str
    size_bytes: int = Field(ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    container: str | None = None
    bitrate: int | None = Field(default=None, ge=0)
    video: VideoStreamResponse
    audio: AudioStreamResponse | None = None
