from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import IncompatibleImageOutputError, InvalidIconSizeError, InvalidImageError
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
    generated_icon_sizes: tuple[int, ...] = ()


class PillowImageConverter:
    """Safe static raster conversion built on the shared Pillow policy."""

    def __init__(self, jpeg_quality: int = 90, webp_quality: int = 88, ico_sizes: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)) -> None:
        self._jpeg_quality = jpeg_quality
        self._webp_quality = webp_quality
        self._ico_sizes = ico_sizes

    def convert(self, source: Path, destination: Path, output: ImageConversionOutputFormat, quality_percent: int | None, background_color: str | None, ico_sizes: tuple[int, ...] | None = None, ico_source_size: int | None = None) -> ConvertedImage:
        image, source_format, source_icon_size = self._load(source, ico_source_size)
        has_alpha = _has_alpha(image)
        background_flattened = False
        if output is ImageConversionOutputFormat.JPEG and has_alpha:
            if background_color is None:
                raise IncompatibleImageOutputError()
            image = _flatten(image, background_color)
            background_flattened = True
        quality = quality_percent or (self._jpeg_quality if output is ImageConversionOutputFormat.JPEG else self._webp_quality)
        payload, generated_icon_sizes = self._encode(image, output, quality, ico_sizes)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return ConvertedImage(output.value.upper().replace("JPEG", "JPEG"), image.width, image.height, _has_alpha(image), has_alpha and output is not ImageConversionOutputFormat.JPEG, background_flattened, source_icon_size, generated_icon_sizes)

    def _load(self, source: Path, requested_icon_size: int | None) -> tuple[Image.Image, str, tuple[int, int] | None]:
        try:
            with Image.open(source) as opened:
                source_format = (opened.format or "").upper()
                source_icon_size = None
                if source_format == "ICO" and hasattr(opened, "ico"):
                    sizes = opened.ico.sizes()
                    if requested_icon_size is not None and (requested_icon_size, requested_icon_size) not in sizes:
                        raise InvalidIconSizeError()
                    source_icon_size = (requested_icon_size, requested_icon_size) if requested_icon_size is not None else max(sizes, key=lambda size: size[0] * size[1])
                    image = opened.ico.getimage(source_icon_size).copy()
                else:
                    opened.load()
                    image = ImageOps.exif_transpose(opened).copy()
                return image, source_format, source_icon_size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidImageError() from exc

    def _encode(self, image: Image.Image, output: ImageConversionOutputFormat, quality: int, requested_icon_sizes: tuple[int, ...] | None) -> tuple[bytes, tuple[int, ...]]:
        stream = BytesIO()
        if output is ImageConversionOutputFormat.PNG:
            image.save(stream, format="PNG", optimize=True, compress_level=9); return stream.getvalue(), ()
        elif output is ImageConversionOutputFormat.JPEG:
            image.convert("RGB").save(stream, format="JPEG", quality=quality, optimize=True, progressive=True); return stream.getvalue(), ()
        elif output is ImageConversionOutputFormat.WEBP:
            image.save(stream, format="WEBP", quality=quality, method=6); return stream.getvalue(), ()
        elif output is ImageConversionOutputFormat.ICO:
            candidates = self._ico_sizes if requested_icon_sizes is None else requested_icon_sizes
            if not candidates or any(size not in self._ico_sizes for size in candidates):
                raise InvalidIconSizeError()
            # Do not create icons larger than the shortest source edge: that would upscale.
            generated = tuple(sorted({size for size in candidates if size <= min(image.width, image.height)}))
            if not generated:
                raise InvalidIconSizeError()
            image.save(stream, format="ICO", sizes=[(size, size) for size in generated])
            return stream.getvalue(), generated
        else:
            raise InvalidImageError()
        raise InvalidImageError()


def _flatten(image: Image.Image, background_color: str) -> Image.Image:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    background = Image.new("RGB", image.size, background_color)
    background.paste(image, mask=image.getchannel("A"))
    return background


def _has_alpha(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info
