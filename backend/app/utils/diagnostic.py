"""Safe local-development readiness checks; run with ``python -m app.utils.diagnostic``."""

import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from redis import Redis

from app.core.config import Settings, get_settings
from app.encoders.ffmpeg_nvidia import detect_nvidia_encoders


class DiagnosticStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    status: DiagnosticStatus
    label: str
    detail: str


def run_diagnostics(settings: Settings | None = None) -> list[DiagnosticResult]:
    """Return non-secret information needed to run the local media pipeline."""
    settings = settings or get_settings()
    results = [DiagnosticResult(DiagnosticStatus.PASS, "Python", platform.python_version())]
    results.extend(_binary_diagnostics("FFmpeg", settings.ffmpeg_binary))
    results.extend(_binary_diagnostics("ffprobe", settings.ffprobe_binary))
    results.append(_redis_diagnostic(settings.redis_url))
    results.append(DiagnosticResult(DiagnosticStatus.PASS, "Storage backend", settings.storage_backend))
    results.append(_writable_directory("Temporary directory", settings.temp_directory))
    if settings.storage_backend == "local":
        results.append(_writable_directory("Local storage directory", settings.temp_directory))
    elif settings.storage_backend == "r2":
        results.append(_r2_configuration_diagnostic(settings))
    else:
        results.append(DiagnosticResult(DiagnosticStatus.FAIL, "Storage backend", "Unsupported backend configured"))
    results.append(_gpu_diagnostic(settings))
    return results


def _binary_diagnostics(label: str, configured_binary: str) -> list[DiagnosticResult]:
    executable = shutil.which(configured_binary)
    if executable is None:
        return [DiagnosticResult(DiagnosticStatus.FAIL, f"{label} path", f"{configured_binary!r} is not available")]
    try:
        completed = subprocess.run([executable, "-version"], capture_output=True, text=True, check=False, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return [DiagnosticResult(DiagnosticStatus.FAIL, f"{label} path", f"{configured_binary!r} could not run")]
    if completed.returncode != 0:
        return [DiagnosticResult(DiagnosticStatus.FAIL, f"{label} path", f"{configured_binary!r} returned an error")]
    version = next((line for line in completed.stdout.splitlines() if line.strip()), "version unavailable")
    return [
        DiagnosticResult(DiagnosticStatus.PASS, f"{label} path", executable),
        DiagnosticResult(DiagnosticStatus.PASS, f"{label} version", version),
    ]


def _redis_diagnostic(redis_url: str) -> DiagnosticResult:
    parsed = urlsplit(redis_url)
    safe_target = f"{parsed.hostname or 'unknown'}:{parsed.port or 6379}"
    try:
        Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
    except Exception:
        return DiagnosticResult(DiagnosticStatus.FAIL, "Redis", f"Not reachable at {safe_target}")
    return DiagnosticResult(DiagnosticStatus.PASS, "Redis", f"Reachable at {safe_target}")


def _writable_directory(label: str, directory: Path) -> DiagnosticResult:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, delete=True):
            pass
    except OSError:
        return DiagnosticResult(DiagnosticStatus.FAIL, label, f"Not writable: {directory}")
    return DiagnosticResult(DiagnosticStatus.PASS, label, f"Writable: {directory}")


def _r2_configuration_diagnostic(settings: Settings) -> DiagnosticResult:
    configured = all((settings.r2_account_id, settings.r2_access_key_id, settings.r2_secret_access_key, settings.r2_bucket_name))
    status = DiagnosticStatus.PASS if configured else DiagnosticStatus.FAIL
    return DiagnosticResult(status, "R2 configuration", "Configured" if configured else "Required R2 settings are incomplete")


def _gpu_diagnostic(settings: Settings) -> DiagnosticResult:
    if not settings.gpu_enabled:
        return DiagnosticResult(DiagnosticStatus.WARNING, "GPU mode", "Disabled")
    encoders = detect_nvidia_encoders(settings.ffmpeg_binary)
    if not encoders:
        return DiagnosticResult(DiagnosticStatus.WARNING, "GPU mode", "Enabled, but no NVENC encoders were detected")
    return DiagnosticResult(DiagnosticStatus.PASS, "GPU mode", f"Enabled; detected: {', '.join(sorted(encoders))}")


def main() -> int:
    results = run_diagnostics()
    for result in results:
        print(f"{result.status:<7} {result.label}: {result.detail}")
    return 1 if any(result.status is DiagnosticStatus.FAIL for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
