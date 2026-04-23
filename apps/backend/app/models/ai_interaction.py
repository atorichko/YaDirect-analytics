from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AIInteraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_interactions"
    __table_args__ = (
        Index("ix_ai_interactions_account_created", "account_id", "created_at"),
        Index("ix_ai_interactions_audit_created", "audit_id", "created_at"),
    )

    audit_id: Mapped[UUID] = mapped_column(ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("ad_accounts.id", ondelete="CASCADE"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="polza.ai")
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
