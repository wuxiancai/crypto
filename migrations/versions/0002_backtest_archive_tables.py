"""backtest archive tables

Revision ID: 0002_backtest_archive
Revises: 0001_v0_1
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_backtest_archive"
down_revision = "0001_v0_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("config_snapshot_id", sa.Integer(), sa.ForeignKey("config_snapshots.id"), nullable=False),
        sa.Column("initial_equity", sa.Numeric(), nullable=False),
        sa.Column("final_equity", sa.Numeric(), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("net_pnl", sa.Numeric(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("backtest_run_id", sa.Integer(), sa.ForeignKey("backtest_runs.id"), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("strategy_type", sa.String(length=64), nullable=False),
        sa.Column("entry_time", sa.BigInteger(), nullable=False),
        sa.Column("exit_time", sa.BigInteger(), nullable=False),
        sa.Column("entry_price", sa.Numeric(), nullable=False),
        sa.Column("exit_price", sa.Numeric(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=False),
        sa.Column("gross_pnl", sa.Numeric(), nullable=False),
        sa.Column("fees", sa.Numeric(), nullable=False),
        sa.Column("funding_fee", sa.Numeric(), nullable=False),
        sa.Column("net_pnl", sa.Numeric(), nullable=False),
        sa.Column("exit_reason", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
