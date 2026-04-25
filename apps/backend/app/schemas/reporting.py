from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field


class AdAccountOut(BaseModel):
    id: UUID
    external_id: str
    name: str
    login: str
    platform: str
    timezone: str
    is_active: bool
    last_audit_at: datetime | None = None


class CampaignOut(BaseModel):
    id: str
    name: str | None = None
    status: str | None = None


class DirectApiUnitsOut(BaseModel):
    account_id: UUID
    account_login: str
    spent: int | None = None
    remaining: int | None = None
    daily_limit: int | None = None
    units_used_login: str | None = None
    units_header_raw: str | None = None


class AdAccountUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class FindingOut(BaseModel):
    id: UUID
    account_id: UUID
    campaign_external_id: str | None
    group_external_id: str | None
    ad_external_id: str | None
    rule_code: str
    rule_name: str
    level: str
    severity: str
    entity_key: str
    issue_location: str
    impact_ru: str
    recommendation_ru: str
    evidence: dict | None = None
    status: str
    suspected_sabotage: bool
    created_at: datetime


class FindingDetailOut(FindingOut):
    audit_id: UUID
    fingerprint: str
    ai_verdict: dict | None = None
    updated_at: datetime
