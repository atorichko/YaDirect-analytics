from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditException(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_exceptions"

    account_id: Mapped[UUID] = mapped_column(ForeignKey("ad_accounts.id", ondelete="CASCADE"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(1024), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
