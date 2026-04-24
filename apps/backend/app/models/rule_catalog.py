from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RuleCatalog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rule_catalogs"
    __table_args__ = (
        UniqueConstraint("version", "platform", name="uq_rule_catalog_version_platform"),
        Index("ix_rule_catalogs_platform_is_active", "platform", "is_active"),
    )

    version: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, default="yandex_direct")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class RuleDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rule_definitions"
    __table_args__ = (
        UniqueConstraint("catalog_id", "rule_code", name="uq_rule_definitions_catalog_rule_code"),
        Index("ix_rule_definitions_code", "rule_code"),
    )

    catalog_id: Mapped[UUID] = mapped_column(ForeignKey("rule_catalogs.id", ondelete="CASCADE"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    fix_recommendation: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    level: Mapped[str] = mapped_column(String(4), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    check_type: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
