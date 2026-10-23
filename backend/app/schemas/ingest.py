from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WhitelistResponse(BaseModel):
    site_id: UUID
    generated_at: datetime
    etag: str
    plates: list[str]
