from app.services.guest_policy_service import ComplexityClass


class ProcessingSelectionService:
    """Select an execution queue without exposing physical worker details to callers."""

    def __init__(
        self,
        gpu_enabled: bool,
        gpu_min_complexity: str,
        gpu_encoders: set[str],
        cpu_queue: str,
        gpu_queue: str,
    ) -> None:
        self.gpu_enabled = gpu_enabled
        self.gpu_min = ComplexityClass(gpu_min_complexity)
        self.gpu_encoders = gpu_encoders
        self.cpu_queue = cpu_queue
        self.gpu_queue = gpu_queue

    def select(self, input_metadata: dict | None) -> str:
        try:
            complexity = ComplexityClass((input_metadata or {}).get("complexity", "standard"))
        except ValueError:
            complexity = ComplexityClass.STANDARD
        order = {
            ComplexityClass.STANDARD: 0,
            ComplexityClass.HEAVY: 1,
            ComplexityClass.VERY_HEAVY: 2,
        }
        if self.gpu_enabled and "h264_nvenc" in self.gpu_encoders and order[complexity] >= order[self.gpu_min]:
            return self.gpu_queue
        return self.cpu_queue
