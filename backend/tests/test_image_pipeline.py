from io import BytesIO
from pathlib import Path
from random import Random

import pytest
from fastapi.testclient import TestClient
from PIL import Image, features

from app.core.exceptions import (
    ImageDimensionsExceededError,
    IncompatibleImageOutputError,
    InvalidImageError,
    InvalidTargetSizeError,
    UnsupportedAnimatedImageError,
)
from app.encoders.image.base import ImageEncoderConfig, ImageEncodingRequest, ImageTargetSizeUnreachable, TargetSizeFailureContext
from app.encoders.image.pillow_encoder import PillowImageEncoder
from app.models.image import ImageCompressionMode, ImageMetadata, ImageOutputFormat, ImageResizeOption, JobTool
from app.models.job import Job
from app.services.image_compression_service import ImageCompressionService
from app.services.image_probe_service import ImageProbeService
from app.services.job_service import JobService
from app.services.upload_service import UploadService
from app.services.video_probe_service import VideoProbeService
from app.storage.local import LocalStorage
from app.repositories.job_repository import InMemoryJobRepository
from app.repositories.upload_repository import InMemoryUploadRepository
from app.workers.image_compression_worker import _process_image_job
from app.api.dependencies import get_image_upload_service, get_upload_service
from app.main import app


def _probe(tmp_path: Path, *, max_pixels: int = 40_000_000) -> ImageProbeService:
    return ImageProbeService(LocalStorage(tmp_path / "storage"), 10 * 1024 * 1024, max_pixels, 8_000, 8_000, tmp_path)


def _config(**overrides: int | float) -> ImageEncoderConfig:
    values: dict[str, int | float] = {
        "min_target_size_bytes": 1_024,
        "max_target_size_bytes": 2 * 1024 * 1024,
        "min_quality": 35,
        "max_quality": 92,
        "target_search_max_attempts": 8,
        "target_resize_max_attempts": 4,
        "target_resize_factor": 0.85,
        "target_min_dimension": 64,
    }
    values.update(overrides)
    return ImageEncoderConfig(**values)  # type: ignore[arg-type]


def _save(path: Path, image: Image.Image, image_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format=image_format)


def _colorful_image(size: tuple[int, int] = (420, 300), *, alpha: bool = False) -> Image.Image:
    width, height = size
    random = Random(42)
    pixels = [
        (random.randrange(256), random.randrange(256), random.randrange(256), (x + y) % 256)
        for y in range(height)
        for x in range(width)
    ]
    image = Image.new("RGBA", size) if alpha else Image.new("RGB", size)
    image.putdata(pixels if alpha else [pixel[:3] for pixel in pixels])
    return image


@pytest.mark.parametrize("filename", ["actual.png", "misleading-name.jpg"])
def test_inspect_uploaded_image_uses_persistent_upload_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str) -> None:
    """The inspect endpoint must resolve the Redis-replaceable upload repository, not process memory."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    storage = LocalStorage(tmp_path / "storage")
    image_probe = ImageProbeService(storage, 10 * 1024 * 1024, 40_000_000, 8_000, 8_000, tmp_path)
    service = UploadService(
        InMemoryUploadRepository(), storage,
        VideoProbeService(storage, "ffprobe", 10 * 1024 * 1024, 30, scratch_directory=tmp_path),
        retention_seconds=3600, signed_url_expiry_seconds=900, max_upload_size_bytes=10 * 1024 * 1024,
        image_probe_service=image_probe, image_max_upload_size_bytes=10 * 1024 * 1024,
    )
    image_bytes = BytesIO(); Image.new("RGBA", (41, 29), (10, 80, 220, 128)).save(image_bytes, format="PNG")
    upload, _ = service.initialize(filename, "image/jpeg")
    app.dependency_overrides[get_upload_service] = lambda: service
    app.dependency_overrides[get_image_upload_service] = lambda: service
    try:
        client = TestClient(app)
        stored = client.put(f"/api/v1/uploads/{upload.id}/content", content=image_bytes.getvalue())
        inspected = client.post(f"/api/v1/images/uploads/{upload.id}/inspect")
    finally:
        app.dependency_overrides.clear()
    assert stored.status_code == 204
    assert inspected.status_code == 200
    payload = inspected.json()
    assert payload["format"] == "PNG"
    assert (payload["width"], payload["height"]) == (41, 29)
    assert payload["has_alpha"] is True


@pytest.mark.parametrize(("image_format", "suffix"), [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")])
def test_probe_supported_images(tmp_path: Path, image_format: str, suffix: str) -> None:
    if image_format == "WEBP" and not features.check("webp"):
        pytest.skip("Pillow WebP support is unavailable")
    source = tmp_path / f"source{suffix}"
    _save(source, Image.new("RGB", (120, 80), "navy"), image_format)
    metadata = _probe(tmp_path).probe(source, filename=source.name)
    assert metadata.format == image_format
    assert (metadata.width, metadata.height) == (120, 80)
    assert not metadata.animated


def test_probe_rejects_malformed_and_animated_images(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.png"; malformed.write_bytes(b"not an image")
    with pytest.raises(InvalidImageError): _probe(tmp_path).probe(malformed)
    animated = tmp_path / "animated.gif"
    Image.new("RGB", (8, 8), "red").save(animated, save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")], duration=100)
    with pytest.raises(UnsupportedAnimatedImageError): _probe(tmp_path).probe(animated)


def test_probe_applies_exif_orientation_and_dimension_limit(tmp_path: Path) -> None:
    source = tmp_path / "rotated.jpg"
    exif = Image.Exif(); exif[274] = 6
    Image.new("RGB", (40, 80), "red").save(source, exif=exif)
    metadata = _probe(tmp_path).probe(source)
    assert (metadata.width, metadata.height) == (80, 40)
    with pytest.raises(ImageDimensionsExceededError): _probe(tmp_path, max_pixels=500).probe(source)


def test_encoder_preserves_alpha_for_webp_and_rejects_jpeg_alpha(tmp_path: Path) -> None:
    if not features.check("webp"):
        pytest.skip("Pillow WebP support is unavailable")
    source = tmp_path / "alpha.png"; _save(source, Image.new("RGBA", (160, 100), (20, 40, 200, 120)), "PNG")
    encoder = PillowImageEncoder()
    with pytest.raises(IncompatibleImageOutputError):
        encoder.compress(ImageEncodingRequest(source, tmp_path / "bad.jpg", ImageCompressionMode.BALANCED, None, ImageOutputFormat.JPEG, ImageResizeOption.KEEP_ORIGINAL, _config()))
    result = encoder.compress(ImageEncodingRequest(source, tmp_path / "output.webp", ImageCompressionMode.BALANCED, None, ImageOutputFormat.WEBP, ImageResizeOption.KEEP_ORIGINAL, _config()))
    assert result.has_alpha and (tmp_path / "output.webp").stat().st_size > 0


@pytest.mark.parametrize("mode", [ImageCompressionMode.BEST_QUALITY, ImageCompressionMode.BALANCED, ImageCompressionMode.SMALLEST_SIZE])
def test_jpeg_modes_and_resize_do_not_upscale(tmp_path: Path, mode: ImageCompressionMode) -> None:
    source = tmp_path / "source.jpg"; _save(source, Image.effect_noise((640, 480), 80).convert("RGB"), "JPEG")
    output = tmp_path / f"{mode}.jpg"
    result = PillowImageEncoder().compress(ImageEncodingRequest(source, output, mode, None, ImageOutputFormat.JPEG, ImageResizeOption.PERCENT_50, _config()))
    assert output.is_file() and output.stat().st_size > 0
    assert (result.width, result.height) == (320, 240)


@pytest.mark.parametrize("target", [50 * 1024, 100 * 1024])
def test_target_size_search_returns_highest_practical_candidate(tmp_path: Path, target: int) -> None:
    source = tmp_path / "source.jpg"; _save(source, Image.effect_noise((640, 480), 90).convert("RGB"), "JPEG")
    output = tmp_path / f"target-{target}.jpg"
    result = PillowImageEncoder().compress(ImageEncodingRequest(source, output, ImageCompressionMode.TARGET_SIZE, target, ImageOutputFormat.JPEG, ImageResizeOption.KEEP_ORIGINAL, _config()))
    assert output.stat().st_size <= target
    assert result.target_achieved


def test_target_size_unreachable_is_bounded(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"; _save(source, Image.effect_noise((600, 600), 100).convert("RGB"), "JPEG")
    with pytest.raises(ImageTargetSizeUnreachable):
        PillowImageEncoder().compress(ImageEncodingRequest(source, tmp_path / "unreachable.jpg", ImageCompressionMode.TARGET_SIZE, 1_024, ImageOutputFormat.JPEG, ImageResizeOption.KEEP_ORIGINAL, _config(min_quality=90, max_quality=90, target_resize_max_attempts=0, target_min_dimension=600)))


def test_probe_upload_cleans_temporary_object(tmp_path: Path) -> None:
    buffer = BytesIO(); Image.new("RGB", (20, 20), "green").save(buffer, format="PNG"); buffer.seek(0)
    service = _probe(tmp_path)
    metadata = service.probe_upload(buffer, "safe.png")
    assert metadata.format == "PNG"
    assert list((tmp_path / "storage" / "uploads").glob("*")) == []


def test_image_compression_service_persists_actual_output_metadata(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")
    source = tmp_path / "source.jpg"; _save(source, Image.effect_noise((640, 480), 85).convert("RGB"), "JPEG")
    storage.put(source, "uploads/source.image")
    probe = _probe(tmp_path)
    service = ImageCompressionService(PillowImageEncoder(), storage, probe, tmp_path, _config())
    job = Job(tool=JobTool.IMAGE, original_filename="source.jpg", input_storage_key="uploads/source.image", compression_mode=ImageCompressionMode.TARGET_SIZE, target_size_bytes=100 * 1024, image_output_format=ImageOutputFormat.JPEG, image_resize=ImageResizeOption.KEEP_ORIGINAL)
    input_metadata = service.probe_input(job)
    outcome = service.compress(job, input_metadata)
    assert storage.object_info(outcome.output_storage_key) is not None
    assert outcome.output_metadata["format"] == "JPEG"
    assert outcome.output_metadata["target_achieved"] is True
    assert outcome.output_metadata["size_bytes"] <= 100 * 1024


def test_image_compression_service_removes_output_when_post_encode_validation_fails(tmp_path: Path) -> None:
    class FailingOutputProbe:
        def probe(self, source: Path, filename: str | None = None):  # type: ignore[no-untyped-def]
            raise InvalidImageError()

    storage = LocalStorage(tmp_path / "storage")
    source = tmp_path / "source.jpg"
    _save(source, Image.effect_noise((640, 480), 85).convert("RGB"), "JPEG")
    storage.put(source, "uploads/source.image")
    input_metadata = _probe(tmp_path).probe(source)
    service = ImageCompressionService(PillowImageEncoder(), storage, FailingOutputProbe(), tmp_path, _config())  # type: ignore[arg-type]
    job = Job(
        tool=JobTool.IMAGE,
        original_filename="source.jpg",
        input_storage_key="uploads/source.image",
        compression_mode=ImageCompressionMode.BALANCED,
        image_output_format=ImageOutputFormat.JPEG,
        image_resize=ImageResizeOption.KEEP_ORIGINAL,
    )

    with pytest.raises(InvalidImageError):
        service.compress(job, input_metadata)

    assert list((tmp_path / "storage" / "outputs").glob("*")) == []


def test_png_modes_use_meaningfully_different_palette_strategies(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    _save(source, _colorful_image(), "PNG")
    encoder = PillowImageEncoder()
    outputs: dict[ImageCompressionMode, Path] = {}
    for mode in (ImageCompressionMode.BEST_QUALITY, ImageCompressionMode.BALANCED, ImageCompressionMode.SMALLEST_SIZE):
        output = tmp_path / f"{mode.value}.png"
        encoder.compress(ImageEncodingRequest(source, output, mode, None, ImageOutputFormat.ORIGINAL, ImageResizeOption.KEEP_ORIGINAL, _config()))
        outputs[mode] = output

    best, balanced, smallest = (outputs[mode] for mode in (ImageCompressionMode.BEST_QUALITY, ImageCompressionMode.BALANCED, ImageCompressionMode.SMALLEST_SIZE))
    assert best.stat().st_size > balanced.stat().st_size > smallest.stat().st_size
    with Image.open(best) as image:
        assert image.mode == "RGB"
    with Image.open(balanced) as image:
        assert image.mode == "P"
    with Image.open(smallest) as image:
        assert image.mode == "P"


def test_png_quantization_preserves_transparency_and_auto_uses_webp(tmp_path: Path) -> None:
    if not features.check("webp"):
        pytest.skip("Pillow WebP support is unavailable")
    source = tmp_path / "source.png"
    _save(source, _colorful_image(alpha=True), "PNG")
    png_output = tmp_path / "balanced.png"
    webp_output = tmp_path / "auto.webp"
    encoder = PillowImageEncoder()
    encoder.compress(ImageEncodingRequest(source, png_output, ImageCompressionMode.BALANCED, None, ImageOutputFormat.ORIGINAL, ImageResizeOption.KEEP_ORIGINAL, _config()))
    auto = encoder.compress(ImageEncodingRequest(source, webp_output, ImageCompressionMode.BALANCED, None, ImageOutputFormat.AUTO, ImageResizeOption.KEEP_ORIGINAL, _config()))
    assert _probe(tmp_path).probe(png_output).has_alpha
    assert auto.format == "WEBP"
    assert _probe(tmp_path).probe(webp_output).has_alpha


@pytest.mark.parametrize(("image_format", "output_format"), [("JPEG", ImageOutputFormat.JPEG), ("WEBP", ImageOutputFormat.WEBP)])
def test_quality_override_changes_lossy_output_size(tmp_path: Path, image_format: str, output_format: ImageOutputFormat) -> None:
    if image_format == "WEBP" and not features.check("webp"):
        pytest.skip("Pillow WebP support is unavailable")
    source = tmp_path / f"source.{image_format.lower()}"
    _save(source, _colorful_image(), image_format)
    encoder = PillowImageEncoder()
    high = tmp_path / "high.out"
    low = tmp_path / "low.out"
    encoder.compress(ImageEncodingRequest(source, high, ImageCompressionMode.BALANCED, None, output_format, ImageResizeOption.KEEP_ORIGINAL, _config(), quality_percent=90))
    encoder.compress(ImageEncodingRequest(source, low, ImageCompressionMode.BALANCED, None, output_format, ImageResizeOption.KEEP_ORIGINAL, _config(), quality_percent=30))
    assert high.stat().st_size > low.stat().st_size


def test_requested_percentage_and_custom_dimensions_preserve_aspect_ratio_and_do_not_upscale(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    _save(source, _colorful_image((400, 200)), "JPEG")
    encoder = PillowImageEncoder()
    percentage = encoder.compress(ImageEncodingRequest(source, tmp_path / "percent.jpg", ImageCompressionMode.BALANCED, None, ImageOutputFormat.JPEG, ImageResizeOption.PERCENTAGE, _config(), resize_percent=75))
    custom = encoder.compress(ImageEncodingRequest(source, tmp_path / "custom.jpg", ImageCompressionMode.BALANCED, None, ImageOutputFormat.JPEG, ImageResizeOption.CUSTOM, _config(), custom_width=200))
    assert (percentage.width, percentage.height) == (300, 150)
    assert (custom.width, custom.height) == (200, 100)
    with pytest.raises(InvalidTargetSizeError):
        encoder.compress(ImageEncodingRequest(source, tmp_path / "upscale.jpg", ImageCompressionMode.BALANCED, None, ImageOutputFormat.JPEG, ImageResizeOption.CUSTOM, _config(), custom_width=800))


def test_target_respects_quality_floor_and_resize_permission(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    _save(source, _colorful_image((800, 600)), "JPEG")
    encoder = PillowImageEncoder()
    request = ImageEncodingRequest(source, tmp_path / "no-resize.jpg", ImageCompressionMode.TARGET_SIZE, 10 * 1024, ImageOutputFormat.JPEG, ImageResizeOption.KEEP_ORIGINAL, _config(target_resize_max_attempts=4), quality_percent=90, allow_resize_for_target=False)
    with pytest.raises(ImageTargetSizeUnreachable):
        encoder.compress(request)
    result = encoder.compress(ImageEncodingRequest(source, tmp_path / "resize.jpg", ImageCompressionMode.TARGET_SIZE, 10 * 1024, ImageOutputFormat.JPEG, ImageResizeOption.KEEP_ORIGINAL, _config(target_resize_max_attempts=8), quality_percent=35, allow_resize_for_target=True))
    assert result.target_achieved and result.resized_for_target
    assert (tmp_path / "resize.jpg").stat().st_size <= 10 * 1024


def test_large_rgb_png_reaches_100kb_with_auto_quality_and_resize(tmp_path: Path) -> None:
    source = tmp_path / "browser-class.png"
    _save(source, _colorful_image((1448, 1086)), "PNG")
    output = tmp_path / "target.png"
    progress: list[int] = []
    result = PillowImageEncoder().compress(
        ImageEncodingRequest(
            source,
            output,
            ImageCompressionMode.TARGET_SIZE,
            100 * 1024,
            ImageOutputFormat.ORIGINAL,
            ImageResizeOption.KEEP_ORIGINAL,
            _config(target_resize_max_attempts=10, target_min_dimension=32),
            allow_resize_for_target=True,
            on_progress=progress.append,
        )
    )
    assert result.format == "PNG"
    assert output.stat().st_size <= 100 * 1024
    assert result.target_achieved and result.resized_for_target
    assert result.width / result.height == pytest.approx(1448 / 1086, rel=0.01)
    assert progress and progress == sorted(progress) and progress[-1] <= 90


def test_explicit_png_quality_floor_without_resize_can_remain_unreachable(tmp_path: Path) -> None:
    source = tmp_path / "floor.png"
    _save(source, _colorful_image((900, 675)), "PNG")
    with pytest.raises(ImageTargetSizeUnreachable) as raised:
        PillowImageEncoder().compress(
            ImageEncodingRequest(
                source,
                tmp_path / "floor-target.png",
                ImageCompressionMode.TARGET_SIZE,
                20 * 1024,
                ImageOutputFormat.ORIGINAL,
                ImageResizeOption.KEEP_ORIGINAL,
                _config(),
                quality_percent=80,
                allow_resize_for_target=False,
            )
        )
    context = raised.value.context
    assert context.quality_floor_was_explicit
    assert not context.resize_allowed
    assert context.output_format == "PNG"
    assert context.smallest_achieved_bytes > 20 * 1024


def test_automatic_png_target_search_can_reach_20kb_before_absolute_limit(tmp_path: Path) -> None:
    source = tmp_path / "stress.png"
    _save(source, _colorful_image((900, 675)), "PNG")
    output = tmp_path / "stress-target.png"
    result = PillowImageEncoder().compress(
        ImageEncodingRequest(
            source,
            output,
            ImageCompressionMode.TARGET_SIZE,
            20 * 1024,
            ImageOutputFormat.ORIGINAL,
            ImageResizeOption.KEEP_ORIGINAL,
            _config(target_resize_max_attempts=10, target_min_dimension=32),
            allow_resize_for_target=True,
        )
    )
    assert result.target_achieved
    assert output.stat().st_size <= 20 * 1024


def test_target_size_failure_persists_safe_context_and_message() -> None:
    class TargetFailingService:
        def probe_input(self, _: Job):
            return ImageMetadata("source.png", 2_059_224, "PNG", 1448, 1086, "RGB", False, False, 1)

        def compress(self, _: Job, __: ImageMetadata, on_progress=None):
            if on_progress:
                on_progress(70)
            raise ImageTargetSizeUnreachable(
                TargetSizeFailureContext(102_400, 108_427, 754, 566, "PNG", False, True)
            )

        def discard_output(self, _: str) -> None:
            pass

    job_service = JobService(InMemoryJobRepository())
    job = job_service.create_image_job(
        "source.png",
        ImageCompressionMode.TARGET_SIZE,
        102_400,
        ImageOutputFormat.ORIGINAL,
        ImageResizeOption.KEEP_ORIGINAL,
    )
    _process_image_job(job.id, job_service, TargetFailingService())  # type: ignore[arg-type]
    failed = job_service.get(job.id)
    assert failed.status.value == "failed"
    assert failed.error_code == "target_size_unreachable"
    assert failed.safe_error_message == "We couldn’t reach 100 KB with the selected format and limits."
    assert failed.target_failure_context == {
        "requested_target_bytes": 102_400,
        "smallest_achieved_bytes": 108_427,
        "smallest_width": 754,
        "smallest_height": 566,
        "output_format": "PNG",
        "quality_floor_was_explicit": False,
        "resize_allowed": True,
    }
