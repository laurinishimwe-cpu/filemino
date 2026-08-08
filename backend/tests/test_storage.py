from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from app.storage.local import LocalStorage
from app.storage.r2 import R2Storage


def test_local_storage_has_generated_upload_and_private_object_behavior(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = "uploads/server-generated.mp4"; expires_at = datetime.now(UTC) + timedelta(minutes=5)
    signed = storage.create_upload_url(key, uuid4(), expires_at, "video/mp4")
    assert signed.url.startswith("/api/v1/uploads/")
    assert storage.put_stream(BytesIO(b"video"), key, 100) == 5
    assert storage.object_info(key).size_bytes == 5
    destination = tmp_path / "scratch" / "input"
    assert storage.download_to(key, destination).read_bytes() == b"video"
    storage.delete(key)
    assert storage.object_info(key) is None


def test_r2_storage_uses_presigned_urls_and_provider_methods(monkeypatch, tmp_path: Path) -> None:
    class Client:
        def __init__(self): self.calls = []
        def generate_presigned_url(self, operation, Params, ExpiresIn): self.calls.append((operation, Params, ExpiresIn)); return "https://signed.example"
        def head_object(self, **kwargs): return {"ContentLength": 42, "ContentType": "video/mp4"}
        def download_file(self, bucket, key, destination): Path(destination).write_bytes(b"video")
        def upload_file(self, source, bucket, key): self.calls.append(("upload_file", key))
        def delete_object(self, **kwargs): self.calls.append(("delete", kwargs["Key"]))
        def put_object(self, **kwargs): self.calls.append(("put", kwargs["Key"]))
    client = Client(); monkeypatch.setattr("app.storage.r2.boto3.client", lambda *args, **kwargs: client)
    storage = R2Storage("account", "key", "secret", "bucket")
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    assert storage.create_upload_url("uploads/id.mp4", uuid4(), expires_at, "video/mp4").url == "https://signed.example"
    assert storage.create_download_url("outputs/id.mp4", expires_at).url == "https://signed.example"
    assert storage.object_info("uploads/id.mp4").size_bytes == 42
    assert storage.download_to("uploads/id.mp4", tmp_path / "output").read_bytes() == b"video"
    assert [call[0] for call in client.calls[:2]] == ["put_object", "get_object"]
