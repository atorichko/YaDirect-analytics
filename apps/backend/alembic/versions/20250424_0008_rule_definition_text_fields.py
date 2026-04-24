"""add description and recommendation to rule definitions

Revision ID: 20250424_0008
Revises: 20250424_0007
Create Date: 2026-04-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250424_0008"
down_revision: Union[str, Sequence[str], None] = "20250424_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rule_definitions", sa.Column("rule_description", sa.String(length=512), nullable=True))
    op.add_column("rule_definitions", sa.Column("fix_recommendation", sa.String(length=4096), nullable=True))


def downgrade() -> None:
    op.drop_column("rule_definitions", "fix_recommendation")
    op.drop_column("rule_definitions", "rule_description")
