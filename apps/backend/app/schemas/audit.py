from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RunL1AuditRequest(BaseModel):
    account_id: UUID


class RunL1AuditResponse(BaseModel):
    audit_id: UUID
    account_id: UUID
    catalog_version: str
    status: str
    findings_created: int
    started_at: datetime | None
    finished_at: datetime | None


class RunL2AuditRequest(BaseModel):
    account_id: UUID


class RunL2AuditResponse(BaseModel):
    audit_id: UUID
    account_id: UUID
    catalog_version: str
    status: str
    findings_created: int
    started_at: datetime | None
    finished_at: datetime | None


class RunL3AuditRequest(BaseModel):
    account_id: UUID


class RunL3AuditResponse(BaseModel):
    audit_id: UUID
    account_id: UUID
    catalog_version: str
    status: str
    findings_created: int
    started_at: datetime | None
    finished_at: datetime | None


class RunAIAuditRequest(BaseModel):
    account_id: UUID
    max_entities: int = 20


class RunAIAuditResponse(BaseModel):
    audit_id: UUID
    account_id: UUID
    catalog_version: str
    status: str
    findings_created: int
    ai_calls_total: int
    ai_calls_failed: int
    started_at: datetime | None
    finished_at: datetime | None


class QueueAuditJobRequest(BaseModel):
    account_id: UUID
    max_entities: int = 20


class QueueAuditJobResponse(BaseModel):
    task_id: str
    task_name: str
    status: str


class QueueWeeklyJobResponse(BaseModel):
    task_id: str
    task_name: str
    status: str


class JobStatusResponse(BaseModel):
    task_id: str
    state: str
    ready: bool
    successful: bool | None
    result: dict | str | None
    progress_percent: int | None = None
    current_step: str | None = None


class QueueCampaignAuditJobRequest(BaseModel):
    account_id: UUID
    campaign_id: str
    max_entities: int = 20


class QueueCampaignBatchAuditJobRequest(BaseModel):
    account_id: UUID
    max_entities: int = 20


class AccountAutostartSettings(BaseModel):
    enabled: bool
    every_n_days: int
    start_date: str
