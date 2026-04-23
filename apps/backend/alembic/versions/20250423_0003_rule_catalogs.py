"""add rule catalogs and definitions

Revision ID: 20250423_0003
Revises: 20250423_0002
Create Date: 2025-04-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20250423_0003"
down_revision: Union[str, Sequence[str], None] = "20250423_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rule_catalogs",
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False, server_default="yandex_direct"),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", "platform", name="uq_rule_catalog_version_platform"),
    )
    op.create_index(
        "ix_rule_catalogs_platform_is_active",
        "rule_catalogs",
        ["platform", "is_active"],
        unique=False,
    )

    op.create_table(
        "rule_definitions",
        sa.Column("catalog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=4), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("check_type", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["catalog_id"], ["rule_catalogs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_id", "rule_code", name="uq_rule_definitions_catalog_rule_code"),
    )
    op.create_index("ix_rule_definitions_code", "rule_definitions", ["rule_code"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rule_definitions_code", table_name="rule_definitions")
    op.drop_table("rule_definitions")

    op.drop_index("ix_rule_catalogs_platform_is_active", table_name="rule_catalogs")
    op.drop_table("rule_catalogs")
