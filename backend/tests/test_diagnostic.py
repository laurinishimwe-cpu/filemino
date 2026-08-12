from pathlib import Path

from app.core.config import Settings
from app.utils.diagnostic import DiagnosticStatus, run_diagnostics


def test_diagnostic_reports_missing_media_binaries_without_secrets(tmp_path: Path) -> None:
    settings = Settings(
        temp_directory=tmp_path,
        ffmpeg_binary="missing-filemino-ffmpeg",
        ffprobe_binary="missing-filemino-ffprobe",
        redis_url="redis://user:secret@localhost:6379/0",
    )

    results = run_diagnostics(settings)
    rendered = "\n".join(f"{result.label}: {result.detail}" for result in results)

    assert any(result.status is DiagnosticStatus.FAIL and result.label == "FFmpeg path" for result in results)
    assert any(result.status is DiagnosticStatus.FAIL and result.label == "ffprobe path" for result in results)
    assert "secret" not in rendered
    assert "Writable" in rendered
