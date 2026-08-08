import subprocess
from dataclasses import dataclass

from app.encoders.base import EncodingRequest
from app.encoders.ffmpeg_cpu import FFmpegCPUEncoder


@dataclass(frozen=True, slots=True)
class NvidiaPreset:
    preset: str
    cq: int
    audio_bitrate: int


# NVENC CQ values are deliberately independent from x264 CRF settings.
NVIDIA_PRESETS = {
    "best_quality": NvidiaPreset("p5", 19, 160_000),
    "balanced": NvidiaPreset("p4", 23, 128_000),
    "smallest_size": NvidiaPreset("p3", 28, 96_000),
}
SUPPORTED_NVIDIA_ENCODERS = ("h264_nvenc", "hevc_nvenc", "av1_nvenc")


def detect_nvidia_encoders(binary: str) -> set[str]:
    """Return NVENC encoders advertised by the configured FFmpeg binary."""
    try:
        output = subprocess.run(
            [binary, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()

    return {name for name in SUPPORTED_NVIDIA_ENCODERS if name in output}


class FFmpegNvidiaEncoder(FFmpegCPUEncoder):
    """Optional NVENC implementation that preserves FluxFile's MP4/H.264 contract."""

    def __init__(self, binary: str, timeout_seconds: int, available: set[str] | None = None) -> None:
        super().__init__(binary, timeout_seconds)
        self.available = available if available is not None else detect_nvidia_encoders(binary)
        if "h264_nvenc" not in self.available:
            raise RuntimeError("NVIDIA H.264 encoding is unavailable")

    def build_command(self, request: EncodingRequest) -> list[str]:
        command = super().build_command(request)
        preset = NVIDIA_PRESETS[request.mode.value]
        command[command.index("libx264")] = "h264_nvenc"
        command[command.index("-preset") + 1] = preset.preset
        command[command.index("-b:a") + 1] = str(preset.audio_bitrate)
        if "-crf" in command:
            command[command.index("-crf")] = "-cq"
            command[command.index("-cq") + 1] = str(preset.cq)
        return command
