"""paper runtime events

Revision ID: 0004_paper_runtime_events
Revises: 0003_config_snapshot_content
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_paper_runtime_events"
down_revision = "0003_config_snapshot_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_runtime_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("event_time", sa.BigInteger(), nullable=False),
        sa.Column("strategy_type", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("paper_runtime_events")
