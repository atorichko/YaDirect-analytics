"""add ai interactions table

Revision ID: 20250423_0004
Revises: 20250423_0003
Create Date: 2025-04-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20250423_0004"
down_revision: Union[str, Sequence[str], None] = "20250423_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_interactions",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="polza.ai"),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response_raw", sa.Text(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["ad_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_interactions_account_created", "ai_interactions", ["account_id", "created_at"], unique=False)
    op.create_index("ix_ai_interactions_audit_created", "ai_interactions", ["audit_id", "created_at"], unique=False)
    op.create_index("ix_ai_interactions_rule_code", "ai_interactions", ["rule_code"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_interactions_rule_code", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_audit_created", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_account_created", table_name="ai_interactions")
    op.drop_table("ai_interactions")
