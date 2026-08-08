from app.encoders.ffmpeg_nvidia import FFmpegNvidiaEncoder, detect_nvidia_encoders
from app.encoders.base import EncodingRequest
from app.models.video import CompressionMode, ResolutionOption
from pathlib import Path
def test_detection_parses_available_nvenc_encoders(monkeypatch):
    class Result: stdout=" V....D h264_nvenc\n V....D av1_nvenc\n"
    monkeypatch.setattr("app.encoders.ffmpeg_nvidia.subprocess.run",lambda *a,**k:Result())
    assert detect_nvidia_encoders("ffmpeg")=={"h264_nvenc","av1_nvenc"}
def test_nvidia_encoder_keeps_h264_output_contract():
    encoder=FFmpegNvidiaEncoder("ffmpeg",60,{"h264_nvenc"})
    command=encoder.build_command(EncodingRequest(Path("in"),Path("out.mp4"),10,CompressionMode.BALANCED,ResolutionOption.ORIGINAL))
    assert command[command.index("-c:v")+1]=="h264_nvenc"
    assert command[command.index("-b:a") + 1] == "128000"


def test_nvidia_encoder_rejects_missing_h264_capability():
    try:
        FFmpegNvidiaEncoder("ffmpeg", 60, {"hevc_nvenc"})
    except RuntimeError as exc:
        assert "unavailable" in str(exc)
    else:
        raise AssertionError("Expected unavailable H.264 NVENC to be rejected")
