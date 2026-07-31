"""add rotatable mobile refresh sessions

Revision ID: 067
Revises: 066
Create Date: 2026-07-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "067"
down_revision: Union[str, None] = "066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "replaced_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mobile_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_mobile_sessions_user_id", "mobile_sessions", ["user_id"])
    op.create_index(
        "ix_mobile_sessions_token_hash", "mobile_sessions", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_mobile_sessions_token_hash", table_name="mobile_sessions")
    op.drop_index("ix_mobile_sessions_user_id", table_name="mobile_sessions")
    op.drop_table("mobile_sessions")
