from datetime import UTC, datetime
from uuid import uuid4
import pytest
from app.core.exceptions import FileTooLargeError, ResolutionNotAllowedError, TooManyActiveJobsError, VideoTooLongError
from app.models.image import ImageCompressionMode, ImageOutputFormat, ImageResizeOption
from app.models.video import VideoMetadata, VideoStreamMetadata
from app.repositories.job_repository import InMemoryJobRepository
from app.services.job_service import JobService
from app.services.guest_policy_service import ComplexityClass, GuestPolicy, GuestPolicyService
from app.services.rate_limit_service import RateLimitService

def metadata(duration=60,height=720,fps=30,codec="h264"):
    return VideoMetadata("x.mp4",100, duration,"mp4",None,VideoStreamMetadata(width=1280,height=height,fps=fps,codec=codec))
def test_policy_boundaries_and_complexity():
    policy=GuestPolicyService(GuestPolicy(100,60,1080,10,2)); policy.validate_size(100)
    assert policy.validate_video(metadata()).value=="standard"
    with pytest.raises(FileTooLargeError):policy.validate_size(101)
    with pytest.raises(VideoTooLongError):policy.validate_video(metadata(duration=61))
    with pytest.raises(ResolutionNotAllowedError):policy.validate_video(metadata(height=1081))
    heavy_policy=GuestPolicyService(GuestPolicy(100,4000,1080,10,2))
    assert heavy_policy.validate_video(metadata(duration=3600,height=1080,fps=60,codec="av1")) is ComplexityClass.VERY_HEAVY

class FakeRedis:
    def __init__(self):self.count={};self.active={}
    def incr(self,k):self.count[k]=self.count.get(k,0)+1;return self.count[k]
    def expire(self,*a):pass
    def eval(self,script,n,key,now,limit,expires,job,ttl):
        values=self.active.setdefault(key,set())
        if len(values)>=int(limit):return 0
        values.add(job);return 1
    def zrem(self,key,job):self.active.get(key,set()).discard(job)
def test_redis_backed_rate_and_concurrency_limits():
    limiter=RateLimitService(FakeRedis(),"salt");subject=limiter.subject_hash("127.0.0.1")
    limiter.consume_job_request(subject,1)
    from app.core.exceptions import RateLimitedError
    with pytest.raises(RateLimitedError):limiter.consume_job_request(subject,1)
    first=uuid4();limiter.claim_concurrent(subject,first,1,60)
    with pytest.raises(TooManyActiveJobsError):limiter.claim_concurrent(subject,uuid4(),1,60)
    limiter.release_concurrent(subject,first);limiter.claim_concurrent(subject,uuid4(),1,60)


def test_image_jobs_use_independent_redis_backed_limits():
    limiter = RateLimitService(FakeRedis(), "salt")
    subject = limiter.subject_hash("127.0.0.1")
    service = JobService(
        InMemoryJobRepository(),
        limiter=limiter,
        max_jobs_per_hour=100,
        max_concurrent_jobs=100,
        image_max_jobs_per_hour=1,
        image_max_concurrent_jobs=1,
    )

    service.create_image_job(
        "photo.jpg",
        ImageCompressionMode.BALANCED,
        None,
        ImageOutputFormat.ORIGINAL,
        ImageResizeOption.KEEP_ORIGINAL,
        client_hash=subject,
    )

    from app.core.exceptions import RateLimitedError
    with pytest.raises(RateLimitedError):
        service.create_image_job(
            "another.jpg",
            ImageCompressionMode.BALANCED,
            None,
            ImageOutputFormat.ORIGINAL,
            ImageResizeOption.KEEP_ORIGINAL,
            client_hash=subject,
        )
