from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuditExceptionCreateRequest(BaseModel):
    account_id: UUID
    rule_code: str = Field(min_length=2, max_length=64)
    entity_key: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=2, max_length=1024)


class AuditExceptionOut(BaseModel):
    id: UUID
    account_id: UUID
    rule_code: str
    entity_key: str
    reason: str
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
