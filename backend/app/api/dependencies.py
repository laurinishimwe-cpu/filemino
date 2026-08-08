from redis import Redis

from app.core.config import get_settings
from app.queue.redis_queue import RedisRQQueue
from app.repositories.job_repository import RedisJobRepository
from app.services.job_service import JobService
from app.services.video_probe_service import VideoProbeService
from app.services.image_probe_service import ImageProbeService
from app.services.upload_service import UploadService
from app.repositories.upload_repository import RedisUploadRepository
from app.storage.factory import create_storage
from app.services.rate_limit_service import RateLimitService
from app.services.guest_policy_service import GuestPolicy, GuestPolicyService
from app.services.processing_selection_service import ProcessingSelectionService


def get_job_service() -> JobService:
    """Compose infrastructure at the API edge; route handlers receive only the service."""
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    repository = RedisJobRepository(redis_client, settings.job_ttl_seconds)
    queue = RedisRQQueue(redis_client, settings.cpu_queue_name, settings.gpu_queue_name, settings.image_queue_name)
    limiter=RateLimitService(redis_client,settings.rate_limit_hash_salt)
    configured_gpu_encoders = {encoder.strip() for encoder in settings.gpu_available_encoders.split(",") if encoder.strip()}
    selector=ProcessingSelectionService(settings.gpu_enabled,settings.gpu_min_complexity,configured_gpu_encoders,settings.cpu_queue_name,settings.gpu_queue_name)
    return JobService(repository, queue, limiter, settings.guest_max_jobs_per_hour, settings.guest_max_concurrent_jobs, settings.job_ttl_seconds, selector, settings.guest_image_max_jobs_per_hour, settings.guest_image_max_concurrent_jobs, settings.image_queue_name)


def get_upload_service() -> UploadService:
    settings = get_settings(); redis_client = Redis.from_url(settings.redis_url); storage = create_storage(settings)
    probe = VideoProbeService(storage, settings.ffprobe_binary, settings.max_upload_size_bytes, settings.ffprobe_timeout_seconds, scratch_directory=settings.temp_directory)
    policy=GuestPolicyService(GuestPolicy(settings.guest_max_upload_size_bytes,settings.guest_max_duration_seconds,settings.guest_max_resolution_height,settings.guest_max_jobs_per_hour,settings.guest_max_concurrent_jobs))
    return UploadService(RedisUploadRepository(redis_client), storage, probe, settings.file_retention_seconds, settings.r2_signed_url_expiry_seconds, settings.max_upload_size_bytes,policy)


def get_image_probe_service() -> ImageProbeService:
    settings = get_settings()
    return ImageProbeService(create_storage(settings), min(settings.max_upload_size_bytes, settings.guest_image_max_upload_size_bytes), min(settings.image_max_pixels, settings.guest_image_max_pixels), settings.image_max_width, settings.image_max_height, settings.temp_directory)


def get_image_upload_service() -> UploadService:
    settings = get_settings(); redis_client = Redis.from_url(settings.redis_url); storage = create_storage(settings)
    video_probe = VideoProbeService(storage, settings.ffprobe_binary, settings.max_upload_size_bytes, settings.ffprobe_timeout_seconds, scratch_directory=settings.temp_directory)
    image_probe = ImageProbeService(storage, min(settings.max_upload_size_bytes, settings.guest_image_max_upload_size_bytes), min(settings.image_max_pixels, settings.guest_image_max_pixels), settings.image_max_width, settings.image_max_height, settings.temp_directory)
    policy = GuestPolicyService(GuestPolicy(settings.guest_max_upload_size_bytes, settings.guest_max_duration_seconds, settings.guest_max_resolution_height, settings.guest_max_jobs_per_hour, settings.guest_max_concurrent_jobs))
    return UploadService(RedisUploadRepository(redis_client), storage, video_probe, settings.file_retention_seconds, settings.r2_signed_url_expiry_seconds, settings.max_upload_size_bytes, policy, image_probe, settings.image_min_target_size_bytes, settings.image_max_target_size_bytes, settings.image_queue_name, min(settings.max_upload_size_bytes, settings.guest_image_max_upload_size_bytes))


def get_storage():
    return create_storage(get_settings())

def get_rate_limiter() -> RateLimitService:
    settings=get_settings(); return RateLimitService(Redis.from_url(settings.redis_url),settings.rate_limit_hash_salt)
