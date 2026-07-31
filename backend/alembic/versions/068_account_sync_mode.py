"""add per-account synchronization and planning mode

Revision ID: 068
Revises: 067
Create Date: 2026-07-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "068"
down_revision: Union[str, None] = "067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("sync_mode", sa.String(length=32), nullable=False, server_default="full"),
    )
    op.execute(
        sa.text("UPDATE accounts SET sync_mode = 'manual' WHERE connection_id IS NULL")
    )
    op.create_check_constraint(
        "ck_accounts_sync_mode",
        "accounts",
        "sync_mode IN ('full', 'balance_only', 'transactions_only', 'manual', 'excluded')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_accounts_sync_mode", "accounts", type_="check")
    op.drop_column("accounts", "sync_mode")
