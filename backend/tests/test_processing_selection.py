from app.services.processing_selection_service import ProcessingSelectionService


def test_standard_jobs_stay_on_cpu_when_gpu_is_reserved_for_heavy_work() -> None:
    selector = ProcessingSelectionService(True, "heavy", {"h264_nvenc"}, "video-cpu", "video-gpu")

    assert selector.select({"complexity": "standard"}) == "video-cpu"


def test_heavy_jobs_use_gpu_when_the_capability_is_configured() -> None:
    selector = ProcessingSelectionService(True, "heavy", {"h264_nvenc"}, "video-cpu", "video-gpu")

    assert selector.select({"complexity": "heavy"}) == "video-gpu"


def test_gpu_disabled_or_unsupported_falls_back_to_cpu() -> None:
    disabled = ProcessingSelectionService(False, "heavy", {"h264_nvenc"}, "video-cpu", "video-gpu")
    unavailable = ProcessingSelectionService(True, "heavy", set(), "video-cpu", "video-gpu")

    assert disabled.select({"complexity": "very_heavy"}) == "video-cpu"
    assert unavailable.select({"complexity": "very_heavy"}) == "video-cpu"
