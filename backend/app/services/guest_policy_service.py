from dataclasses import dataclass
from enum import StrEnum
from app.core.exceptions import FileTooLargeError, ResolutionNotAllowedError, VideoTooLongError
from app.models.video import VideoMetadata
class ComplexityClass(StrEnum): STANDARD="standard"; HEAVY="heavy"; VERY_HEAVY="very_heavy"
@dataclass(frozen=True, slots=True)
class GuestPolicy:
    max_upload_size_bytes:int; max_duration_seconds:int; max_resolution_height:int; max_jobs_per_hour:int; max_concurrent_jobs:int
class VideoComplexityService:
    def classify(self, metadata: VideoMetadata) -> ComplexityClass:
        score=(metadata.video.width or 0)*(metadata.video.height or 0)*(metadata.video.fps or 30)*(metadata.duration_seconds or 0)
        if metadata.video.codec in {"hevc","av1","vp9"}: score*=1.4
        return ComplexityClass.VERY_HEAVY if score>=120_000_000_000 else ComplexityClass.HEAVY if score>=25_000_000_000 else ComplexityClass.STANDARD
class GuestPolicyService:
    def __init__(self, policy:GuestPolicy)->None: self.policy=policy; self.complexity=VideoComplexityService()
    def validate_size(self,size:int)->None:
        if size>self.policy.max_upload_size_bytes: raise FileTooLargeError()
    def validate_video(self,metadata:VideoMetadata)->ComplexityClass:
        if (metadata.duration_seconds or 0)>self.policy.max_duration_seconds: raise VideoTooLongError()
        if (metadata.video.height or 0)>self.policy.max_resolution_height: raise ResolutionNotAllowedError()
        return self.complexity.classify(metadata)
