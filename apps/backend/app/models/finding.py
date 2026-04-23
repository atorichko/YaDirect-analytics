import enum
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FindingSeverity(str, enum.Enum):
    warning = "warning"
    high = "high"
    critical = "critical"


class FindingLevel(str, enum.Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class FindingStatus(str, enum.Enum):
    new = "new"
    existing = "existing"
    fixed = "fixed"
    reopened = "reopened"
    ignored = "ignored"
    false_positive = "false_positive"


class Finding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_audit_status", "audit_id", "status"),
        Index("ix_findings_fingerprint", "fingerprint"),
        Index("ix_findings_account_created", "account_id", "created_at"),
    )

    audit_id: Mapped[UUID] = mapped_column(ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("ad_accounts.id", ondelete="CASCADE"), nullable=False)
    campaign_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    group_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ad_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[FindingLevel] = mapped_column(Enum(FindingLevel, native_enum=False, length=4), nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, native_enum=False, length=16),
        nullable=False,
    )
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    issue_location: Mapped[str] = mapped_column(String(255), nullable=False)
    impact_ru: Mapped[str] = mapped_column(String(2048), nullable=False)
    recommendation_ru: Mapped[str] = mapped_column(String(4096), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, native_enum=False, length=32),
        nullable=False,
        default=FindingStatus.new,
    )
    suspected_sabotage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_verdict: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
