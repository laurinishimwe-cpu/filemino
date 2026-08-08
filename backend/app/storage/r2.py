from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.base import FileStorage, SignedDownload, SignedUpload, StoredObject


class R2Storage(FileStorage):
    """Private Cloudflare R2 storage using the S3-compatible API."""

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        endpoint: str | None = None,
    ) -> None:
        resolved_endpoint = endpoint or f"https://{account_id}.r2.cloudflarestorage.com"
        self._bucket_name = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=resolved_endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def create_upload_url(self, object_key: str, upload_id: UUID, expires_at: datetime, content_type: str | None) -> SignedUpload:
        self._validate_key(object_key)
        params = {"Bucket": self._bucket_name, "Key": object_key}
        if content_type:
            params["ContentType"] = content_type
        seconds = _seconds_until(expires_at)
        return SignedUpload(self._client.generate_presigned_url("put_object", Params=params, ExpiresIn=seconds), expires_at)

    def create_download_url(self, object_key: str, expires_at: datetime) -> SignedDownload:
        self._validate_key(object_key)
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket_name, "Key": object_key},
            ExpiresIn=_seconds_until(expires_at),
        )
        return SignedDownload(url, expires_at)

    def object_info(self, object_key: str) -> StoredObject | None:
        self._validate_key(object_key)
        try:
            response = self._client.head_object(Bucket=self._bucket_name, Key=object_key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return StoredObject(object_key, int(response["ContentLength"]), response.get("ContentType"))

    def put_stream(self, stream: BinaryIO, object_key: str, max_bytes: int) -> int:
        self._validate_key(object_key)
        data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Storage size limit exceeded.")
        self._client.put_object(Bucket=self._bucket_name, Key=object_key, Body=data)
        return len(data)

    def put(self, source: Path, object_key: str) -> str:
        self._validate_key(object_key)
        self._client.upload_file(str(source), self._bucket_name, object_key)
        return object_key

    def download_to(self, object_key: str, destination: Path) -> Path:
        self._validate_key(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self._bucket_name, object_key, str(destination))
        return destination

    def delete(self, object_key: str) -> None:
        self._validate_key(object_key)
        self._client.delete_object(Bucket=self._bucket_name, Key=object_key)

    @staticmethod
    def _validate_key(object_key: str) -> None:
        if not object_key or object_key.startswith("/") or ".." in object_key.split("/"):
            raise ValueError("Invalid storage object key.")


def _seconds_until(expires_at: datetime) -> int:
    return max(1, int((expires_at - datetime.now(expires_at.tzinfo)).total_seconds()))
