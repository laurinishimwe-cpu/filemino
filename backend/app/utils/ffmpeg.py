from pathlib import Path


def ffprobe_arguments(binary: str, source: Path) -> list[str]:
    """Return argument tokens for a future safe subprocess call, never a shell string."""
    return [binary, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(source)]
