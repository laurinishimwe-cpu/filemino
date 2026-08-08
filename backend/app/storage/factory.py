from app.core.config import Settings
from app.storage.base import FileStorage
from app.storage.local import LocalStorage
from app.storage.r2 import R2Storage


def create_storage(settings: Settings) -> FileStorage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.temp_directory, settings.api_prefix)
    if settings.storage_backend == "r2":
        required = [settings.r2_account_id, settings.r2_access_key_id, settings.r2_secret_access_key, settings.r2_bucket_name]
        if any(value is None or value == "" for value in required):
            raise ValueError("R2 storage configuration is incomplete.")
        return R2Storage(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket_name=settings.r2_bucket_name,
            endpoint=settings.r2_endpoint,
        )
    raise ValueError("Unsupported storage backend.")
