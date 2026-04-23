"""add app settings and user full_name

Revision ID: 20250423_0005
Revises: 20250423_0004
Create Date: 2025-04-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250423_0005"
down_revision: Union[str, Sequence[str], None] = "20250423_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))
    op.execute("UPDATE users SET full_name = split_part(email, '@', 1) WHERE full_name IS NULL")
    op.alter_column("users", "full_name", existing_type=sa.String(length=255), nullable=False)
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES ('ai_analysis_prompt', 'Проведи аудит рекламной кампании Яндекс Директ и верни структурированные находки: уровень (L1/L2/L3), severity, краткое объяснение и рекомендацию.')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("users", "full_name")
