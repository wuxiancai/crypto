"""v0.1 core tables

Revision ID: 0001_v0_1
Revises:
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_v0_1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbols",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False, unique=True),
        sa.Column("base_asset", sa.String(length=32)),
        sa.Column("quote_asset", sa.String(length=32)),
        sa.Column("contract_type", sa.String(length=32)),
        sa.Column("status", sa.String(length=32)),
        sa.Column("tick_size", sa.Numeric()),
        sa.Column("step_size", sa.Numeric()),
        sa.Column("min_qty", sa.Numeric()),
        sa.Column("max_qty", sa.Numeric()),
        sa.Column("min_notional", sa.Numeric()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "klines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("open_time", sa.BigInteger(), nullable=False),
        sa.Column("close_time", sa.BigInteger(), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False),
        sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.Numeric(), nullable=False),
        sa.Column("quote_volume", sa.Numeric()),
        sa.Column("trade_count", sa.Integer()),
        sa.Column("taker_buy_base_volume", sa.Numeric()),
        sa.Column("taker_buy_quote_volume", sa.Numeric()),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "interval", "open_time"),
    )
    op.create_table(
        "indicator_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("open_time", sa.BigInteger(), nullable=False),
        sa.Column("ema50", sa.Numeric()),
        sa.Column("ema200", sa.Numeric()),
        sa.Column("adx", sa.Numeric()),
        sa.Column("di_plus", sa.Numeric()),
        sa.Column("di_minus", sa.Numeric()),
        sa.Column("atr", sa.Numeric()),
        sa.Column("atr_pct", sa.Numeric()),
        sa.Column("bb_upper", sa.Numeric()),
        sa.Column("bb_middle", sa.Numeric()),
        sa.Column("bb_lower", sa.Numeric()),
        sa.Column("bb_width_pct", sa.Numeric()),
        sa.Column("volume_ma20", sa.Numeric()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "interval", "open_time"),
    )
    op.create_table(
        "config_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("config_snapshots")
    op.drop_table("indicator_snapshots")
    op.drop_table("klines")
    op.drop_table("symbols")

