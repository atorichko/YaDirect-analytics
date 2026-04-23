import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SnapshotEntityType(str, enum.Enum):
    campaign = "campaign"
    ad_group = "ad_group"
    ad = "ad"
    keyword = "keyword"
    extension = "extension"
    account = "account"


class EntitySnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "entity_snapshots"
    __table_args__ = (
        Index("ix_entity_snapshots_account_type_captured", "account_id", "entity_type", "captured_at"),
        Index("ix_entity_snapshots_content_hash", "content_hash"),
    )

    account_id: Mapped[UUID] = mapped_column(ForeignKey("ad_accounts.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[SnapshotEntityType] = mapped_column(
        Enum(SnapshotEntityType, native_enum=False, length=32),
        nullable=False,
    )
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
