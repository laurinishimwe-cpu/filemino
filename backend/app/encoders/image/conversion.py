from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import IncompatibleImageOutputError, InvalidImageError
from app.models.image import ImageConversionOutputFormat


@dataclass(frozen=True, slots=True)
class ConvertedImage:
    output_format: str
    width: int
    height: int
    has_alpha: bool
    alpha_preserved: bool
    background_flattened: bool
    source_icon_size: tuple[int, int] | None


class PillowImageConverter:
    """Safe static raster conversion built on the shared Pillow policy."""

    def __init__(self, jpeg_quality: int = 90, webp_quality: int = 88, ico_sizes: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)) -> None:
        self._jpeg_quality = jpeg_quality
        self._webp_quality = webp_quality
        self._ico_sizes = ico_sizes

    def convert(self, source: Path, destination: Path, output: ImageConversionOutputFormat, quality_percent: int | None, background_color: str | None) -> ConvertedImage:
        image, source_format, source_icon_size = self._load(source)
        has_alpha = _has_alpha(image)
        background_flattened = False
        if output is ImageConversionOutputFormat.JPEG and has_alpha:
            if background_color is None:
                raise IncompatibleImageOutputError()
            image = _flatten(image, background_color)
            background_flattened = True
        quality = quality_percent or (self._jpeg_quality if output is ImageConversionOutputFormat.JPEG else self._webp_quality)
        payload = self._encode(image, output, quality)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return ConvertedImage(output.value.upper().replace("JPEG", "JPEG"), image.width, image.height, _has_alpha(image), has_alpha and output is not ImageConversionOutputFormat.JPEG, background_flattened, source_icon_size)

    def _load(self, source: Path) -> tuple[Image.Image, str, tuple[int, int] | None]:
        try:
            with Image.open(source) as opened:
                source_format = (opened.format or "").upper()
                source_icon_size = None
                if source_format == "ICO" and hasattr(opened, "ico"):
                    sizes = opened.ico.sizes()
                    source_icon_size = max(sizes, key=lambda size: size[0] * size[1])
                    image = opened.ico.getimage(source_icon_size).copy()
                else:
                    opened.load()
                    image = ImageOps.exif_transpose(opened).copy()
                return image, source_format, source_icon_size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidImageError() from exc

    def _encode(self, image: Image.Image, output: ImageConversionOutputFormat, quality: int) -> bytes:
        stream = BytesIO()
        if output is ImageConversionOutputFormat.PNG:
            image.save(stream, format="PNG", optimize=True, compress_level=9)
        elif output is ImageConversionOutputFormat.JPEG:
            image.convert("RGB").save(stream, format="JPEG", quality=quality, optimize=True, progressive=True)
        elif output is ImageConversionOutputFormat.WEBP:
            image.save(stream, format="WEBP", quality=quality, method=6)
        elif output is ImageConversionOutputFormat.ICO:
            sizes = [(size, size) for size in self._ico_sizes if size <= max(image.width, image.height)]
            image.save(stream, format="ICO", sizes=sizes or [(min(image.width, 256), min(image.height, 256))])
        else:
            raise InvalidImageError()
        return stream.getvalue()


def _flatten(image: Image.Image, background_color: str) -> Image.Image:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    background = Image.new("RGB", image.size, background_color)
    background.paste(image, mask=image.getchannel("A"))
    return background


def _has_alpha(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info
