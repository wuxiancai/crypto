"""store config snapshot content

Revision ID: 0003_config_snapshot_content
Revises: 0002_backtest_archive
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_config_snapshot_content"
down_revision = "0002_backtest_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("config_snapshots", sa.Column("content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("config_snapshots", "content")
