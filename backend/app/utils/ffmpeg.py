import json
import logging
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.core.exceptions import ProbeError

logger = logging.getLogger(__name__)


def ffprobe_arguments(binary: str, source: Path) -> list[str]:
    """Build a fixed ffprobe argument list for a trusted, server-owned file path."""
    return [binary, "-v", "error", "-show_format", "-show_streams", "-of", "json", "-i", str(source)]


def execute_ffprobe(binary: str, source: Path, timeout_seconds: int) -> dict[str, Any]:
    """Run ffprobe without a shell and keep stderr out of public errors."""
    try:
        result = subprocess.run(
            ffprobe_arguments(binary, source),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffprobe could not execute for %s: %s", source.name, exc)
        raise ProbeError() from exc

    if result.returncode != 0:
        logger.warning("ffprobe failed for %s with exit code %s: %s", source.name, result.returncode, result.stderr)
        raise ProbeError()
    return parse_ffprobe_json(result.stdout)


def parse_ffprobe_json(output: str) -> dict[str, Any]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ProbeError() from exc
    if not isinstance(payload, Mapping):
        raise ProbeError()
    return dict(payload)
