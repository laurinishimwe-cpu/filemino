from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UploadInitializeRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=100)


class UploadInitializeResponse(BaseModel):
    upload_id: UUID
    storage_key: str
    upload_url: str
    expires_at: datetime
