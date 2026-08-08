from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class Upload:
    id: UUID = field(default_factory=uuid4)
    storage_key: str = ""
    original_filename: str = ""
    content_type: str | None = None
    client_hash: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
