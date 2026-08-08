from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.core.exceptions import IncompatibleImageOutputError
from app.encoders.image.conversion import PillowImageConverter
from app.models.image import ImageConversionOutputFormat


def _transparent_png(path: Path) -> None:
    image = Image.new("RGBA", (80, 60), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((10, 10, 70, 50), fill=(30, 100, 220, 180))
    image.save(path, format="PNG")


def test_png_to_webp_preserves_alpha(tmp_path: Path) -> None:
    source = tmp_path / "source.png"; destination = tmp_path / "result.webp"
    _transparent_png(source)
    result = PillowImageConverter().convert(source, destination, ImageConversionOutputFormat.WEBP, None, None)
    assert destination.is_file() and destination.stat().st_size > 0
    assert result.alpha_preserved is True
    with Image.open(destination) as image:
        assert image.format == "WEBP"
        assert "A" in image.getbands()


def test_transparent_png_to_jpeg_requires_background(tmp_path: Path) -> None:
    source = tmp_path / "source.png"; _transparent_png(source)
    with pytest.raises(IncompatibleImageOutputError):
        PillowImageConverter().convert(source, tmp_path / "result.jpg", ImageConversionOutputFormat.JPEG, None, None)


def test_transparent_png_to_jpeg_flattens_background(tmp_path: Path) -> None:
    source = tmp_path / "source.png"; destination = tmp_path / "result.jpg"; _transparent_png(source)
    result = PillowImageConverter().convert(source, destination, ImageConversionOutputFormat.JPEG, None, "#ffffff")
    assert result.background_flattened is True
    with Image.open(destination) as image:
        assert image.format == "JPEG" and image.mode == "RGB"


def test_png_to_ico_writes_multiple_icon_sizes(tmp_path: Path) -> None:
    source = tmp_path / "source.png"; destination = tmp_path / "result.ico"
    Image.new("RGBA", (128, 128), (30, 100, 220, 180)).save(source)
    PillowImageConverter().convert(source, destination, ImageConversionOutputFormat.ICO, None, None)
    with Image.open(destination) as image:
        assert image.format == "ICO"
        assert max(image.ico.sizes()) == (128, 128)
