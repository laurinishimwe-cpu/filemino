from dataclasses import dataclass
from enum import StrEnum


class ImageCompressionMode(StrEnum):
    BEST_QUALITY = "best_quality"
    BALANCED = "balanced"
    SMALLEST_SIZE = "smallest_size"
    TARGET_SIZE = "target_size"


class ImageOutputFormat(StrEnum):
    AUTO = "auto"
    ORIGINAL = "original"
    JPEG = "jpeg"
    WEBP = "webp"


class ImageResizeOption(StrEnum):
    KEEP_ORIGINAL = "keep_original"
    PERCENT_75 = "75_percent"
    PERCENT_50 = "50_percent"
    PERCENTAGE = "percentage"
    CUSTOM = "custom"


class ImageConversionOutputFormat(StrEnum):
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    ICO = "ico"


class JobTool(StrEnum):
    VIDEO_COMPRESSION = "video_compression"
    IMAGE_COMPRESSION = "image_compression"
    IMAGE_CONVERSION = "image_conversion"
    VIDEO = VIDEO_COMPRESSION
    IMAGE = IMAGE_COMPRESSION


@dataclass(frozen=True, slots=True)
class ImageFormatCapability:
    format: str
    display_name: str
    extensions: tuple[str, ...]
    mime_types: tuple[str, ...]
    supports_alpha: bool
    supports_animation: bool
    conversion_targets: tuple[ImageConversionOutputFormat, ...]
    recommended_target: ImageConversionOutputFormat


IMAGE_FORMAT_CAPABILITIES: dict[str, ImageFormatCapability] = {
    "PNG": ImageFormatCapability("PNG", "PNG", (".png",), ("image/png",), True, False, (ImageConversionOutputFormat.JPEG, ImageConversionOutputFormat.WEBP, ImageConversionOutputFormat.ICO), ImageConversionOutputFormat.WEBP),
    "JPEG": ImageFormatCapability("JPEG", "JPG", (".jpg", ".jpeg"), ("image/jpeg",), False, False, (ImageConversionOutputFormat.PNG, ImageConversionOutputFormat.WEBP, ImageConversionOutputFormat.ICO), ImageConversionOutputFormat.WEBP),
    "WEBP": ImageFormatCapability("WEBP", "WebP", (".webp",), ("image/webp",), True, False, (ImageConversionOutputFormat.PNG, ImageConversionOutputFormat.JPEG, ImageConversionOutputFormat.ICO), ImageConversionOutputFormat.PNG),
    "ICO": ImageFormatCapability("ICO", "ICO", (".ico",), ("image/x-icon", "image/vnd.microsoft.icon"), True, False, (ImageConversionOutputFormat.PNG, ImageConversionOutputFormat.JPEG, ImageConversionOutputFormat.WEBP), ImageConversionOutputFormat.PNG),
    "BMP": ImageFormatCapability("BMP", "BMP", (".bmp",), ("image/bmp",), False, False, (ImageConversionOutputFormat.PNG, ImageConversionOutputFormat.JPEG, ImageConversionOutputFormat.WEBP), ImageConversionOutputFormat.PNG),
    "TIFF": ImageFormatCapability("TIFF", "TIFF", (".tif", ".tiff"), ("image/tiff",), True, False, (ImageConversionOutputFormat.PNG, ImageConversionOutputFormat.JPEG, ImageConversionOutputFormat.WEBP), ImageConversionOutputFormat.PNG),
}


def image_format_capability(image_format: str) -> ImageFormatCapability | None:
    return IMAGE_FORMAT_CAPABILITIES.get(image_format.upper())


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    filename: str
    size_bytes: int
    format: str
    width: int
    height: int
    mode: str
    has_alpha: bool
    animated: bool
    frame_count: int


def resolve_image_output_format(
    requested: ImageOutputFormat,
    source_format: str,
    has_alpha: bool,
    mode: ImageCompressionMode,
) -> str:
    """Choose the concrete encoder format for an image request.

    ``AUTO`` is intentionally predictable: it retains the source for the
    least aggressive mode, uses WebP for PNG compression work (which also
    keeps alpha), and otherwise retains the already-lossy source format.
    """
    normalized = source_format.upper()
    if requested is ImageOutputFormat.JPEG:
        return "JPEG"
    if requested is ImageOutputFormat.WEBP:
        return "WEBP"
    if requested is ImageOutputFormat.ORIGINAL:
        return normalized
    if normalized == "PNG" and mode is not ImageCompressionMode.BEST_QUALITY:
        return "WEBP"
    if has_alpha:
        return "WEBP"
    return normalized
