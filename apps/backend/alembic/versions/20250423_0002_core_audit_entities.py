"""create core audit entities

Revision ID: 20250423_0002
Revises: 20250423_0001
Create Date: 2025-04-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20250423_0002"
down_revision: Union[str, Sequence[str], None] = "20250423_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ad_accounts",
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("login", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False, server_default="yandex_direct"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ad_accounts_external_id", "ad_accounts", ["external_id"], unique=True)
    op.create_index("ix_ad_accounts_login", "ad_accounts", ["login"], unique=True)

    op.create_table(
        "account_credentials",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="yandex_direct"),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["ad_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "provider", name="uq_account_credentials_account_provider"),
    )
    op.create_index("ix_account_credentials_account_id", "account_credentials", ["account_id"], unique=False)

    op.create_table(
        "entity_snapshots",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("raw_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["ad_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entity_snapshots_entity_key", "entity_snapshots", ["entity_key"], unique=False)
    op.create_index(
        "ix_entity_snapshots_account_type_captured",
        "entity_snapshots",
        ["account_id", "entity_type", "captured_at"],
        unique=False,
    )
    op.create_index("ix_entity_snapshots_content_hash", "entity_snapshots", ["content_hash"], unique=False)
    op.create_index("ix_entity_snapshots_captured_at", "entity_snapshots", ["captured_at"], unique=False)

    op.create_table(
        "audits",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("catalog_version", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["ad_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audits_status", "audits", ["status"], unique=False)
    op.create_index("ix_audits_account_created", "audits", ["account_id", "created_at"], unique=False)

    op.create_table(
        "findings",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_external_id", sa.String(length=128), nullable=True),
        sa.Column("group_external_id", sa.String(length=128), nullable=True),
        sa.Column("ad_external_id", sa.String(length=128), nullable=True),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=4), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("issue_location", sa.String(length=255), nullable=False),
        sa.Column("impact_ru", sa.String(length=2048), nullable=False),
        sa.Column("recommendation_ru", sa.String(length=4096), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("suspected_sabotage", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ai_verdict", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["ad_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_rule_code", "findings", ["rule_code"], unique=False)
    op.create_index("ix_findings_audit_status", "findings", ["audit_id", "status"], unique=False)
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"], unique=False)
    op.create_index("ix_findings_account_created", "findings", ["account_id", "created_at"], unique=False)

    op.create_table(
        "audit_exceptions",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=1024), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["ad_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "rule_code", "entity_key", name="uq_audit_exceptions_key"),
    )
    op.create_index("ix_audit_exceptions_rule_code", "audit_exceptions", ["rule_code"], unique=False)
    op.create_index("ix_audit_exceptions_entity_key", "audit_exceptions", ["entity_key"], unique=False)

    op.create_table(
        "action_logs",
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["ad_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_logs_actor_created", "action_logs", ["actor_user_id", "created_at"], unique=False)
    op.create_index("ix_action_logs_account_created", "action_logs", ["account_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_action_logs_account_created", table_name="action_logs")
    op.drop_index("ix_action_logs_actor_created", table_name="action_logs")
    op.drop_table("action_logs")

    op.drop_index("ix_audit_exceptions_entity_key", table_name="audit_exceptions")
    op.drop_index("ix_audit_exceptions_rule_code", table_name="audit_exceptions")
    op.drop_table("audit_exceptions")

    op.drop_index("ix_findings_account_created", table_name="findings")
    op.drop_index("ix_findings_fingerprint", table_name="findings")
    op.drop_index("ix_findings_audit_status", table_name="findings")
    op.drop_index("ix_findings_rule_code", table_name="findings")
    op.drop_table("findings")

    op.drop_index("ix_audits_account_created", table_name="audits")
    op.drop_index("ix_audits_status", table_name="audits")
    op.drop_table("audits")

    op.drop_index("ix_entity_snapshots_captured_at", table_name="entity_snapshots")
    op.drop_index("ix_entity_snapshots_content_hash", table_name="entity_snapshots")
    op.drop_index("ix_entity_snapshots_account_type_captured", table_name="entity_snapshots")
    op.drop_index("ix_entity_snapshots_entity_key", table_name="entity_snapshots")
    op.drop_table("entity_snapshots")

    op.drop_index("ix_account_credentials_account_id", table_name="account_credentials")
    op.drop_table("account_credentials")

    op.drop_index("ix_ad_accounts_login", table_name="ad_accounts")
    op.drop_index("ix_ad_accounts_external_id", table_name="ad_accounts")
    op.drop_table("ad_accounts")
