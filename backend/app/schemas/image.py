from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

from app.models.image import ImageCompressionMode, ImageConversionOutputFormat, ImageOutputFormat, ImageResizeOption


class ImageCompressionOptions(BaseModel):
    compression_mode: ImageCompressionMode = ImageCompressionMode.BALANCED
    target_size_bytes: int | None = Field(default=None, gt=0)
    output_format: ImageOutputFormat = ImageOutputFormat.ORIGINAL
    resize: ImageResizeOption = ImageResizeOption.KEEP_ORIGINAL
    quality_percent: int | None = Field(default=None, ge=1, le=100)
    resize_percent: int | None = Field(default=None, ge=1, le=100)
    custom_width: int | None = Field(default=None, ge=1)
    custom_height: int | None = Field(default=None, ge=1)
    lock_aspect_ratio: bool = True
    allow_resize_for_target: bool = True


class ImageJobCreateRequest(ImageCompressionOptions):
    upload_id: UUID


class ImageConversionJobCreateRequest(BaseModel):
    upload_id: UUID
    output_format: ImageConversionOutputFormat
    quality_percent: int | None = Field(default=None, ge=1, le=100)
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class ImageMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str
    size_bytes: int = Field(ge=0)
    format: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    mode: str
    has_alpha: bool
    animated: bool
    frame_count: int = Field(ge=1)
