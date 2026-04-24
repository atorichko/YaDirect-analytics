from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RuleDefinitionIn(BaseModel):
    rule_code: str = Field(min_length=1, max_length=64)
    rule_name: str = Field(min_length=1, max_length=255)
    rule_description: str | None = Field(default=None, max_length=512)
    fix_recommendation: str | None = Field(default=None, max_length=4096)
    level: str = Field(pattern="^(L1|L2|L3)$")
    severity: str = Field(pattern="^(warning|high|critical)$")
    check_type: str = Field(pattern="^(deterministic|ai_assisted)$")
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class CatalogUploadRequest(BaseModel):
    catalog_version: str = Field(min_length=1, max_length=32)
    platform: str = Field(default="yandex_direct", min_length=1, max_length=64)
    included_levels: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None, max_length=512)
    rules: list[RuleDefinitionIn] = Field(default_factory=list)


class RuleDefinitionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    rule_code: str
    rule_name: str
    rule_description: str | None
    fix_recommendation: str | None
    level: str
    severity: str
    check_type: str
    enabled: bool
    config: dict


class CatalogSummaryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    version: str
    platform: str
    description: str | None
    is_active: bool
    created_at: datetime


class CatalogWithRulesOut(CatalogSummaryOut):
    included_levels: list[str] = Field(default_factory=list)
    source_payload: dict
    rules: list[RuleDefinitionOut] = Field(default_factory=list)
