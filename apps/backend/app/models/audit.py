import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditTrigger(str, enum.Enum):
    manual = "manual"
    weekly = "weekly"


class AuditStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class Audit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audits"
    __table_args__ = (
        Index("ix_audits_account_created", "account_id", "created_at"),
        Index("ix_audits_status", "status"),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger: Mapped[AuditTrigger] = mapped_column(
        Enum(AuditTrigger, native_enum=False, length=16),
        nullable=False,
    )
    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus, native_enum=False, length=16),
        nullable=False,
        default=AuditStatus.queued,
    )
    catalog_version: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initiated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
