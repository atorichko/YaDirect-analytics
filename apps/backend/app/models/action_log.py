from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ActionLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "action_logs"
    __table_args__ = (
        Index("ix_action_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_action_logs_account_created", "account_id", "created_at"),
    )

    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ad_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
