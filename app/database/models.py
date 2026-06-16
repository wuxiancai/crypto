from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, MetaData, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    base_asset: Mapped[str | None] = mapped_column(String(32))
    quote_asset: Mapped[str | None] = mapped_column(String(32))
    contract_type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32))
    tick_size: Mapped[float | None] = mapped_column(Numeric)
    step_size: Mapped[float | None] = mapped_column(Numeric)
    min_qty: Mapped[float | None] = mapped_column(Numeric)
    max_qty: Mapped[float | None] = mapped_column(Numeric)
    min_notional: Mapped[float | None] = mapped_column(Numeric)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KlineRecord(Base):
    __tablename__ = "klines"
    __table_args__ = (UniqueConstraint("symbol", "interval", "open_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    open_time: Mapped[int] = mapped_column(nullable=False)
    close_time: Mapped[int] = mapped_column(nullable=False)
    open: Mapped[float] = mapped_column(Numeric, nullable=False)
    high: Mapped[float] = mapped_column(Numeric, nullable=False)
    low: Mapped[float] = mapped_column(Numeric, nullable=False)
    close: Mapped[float] = mapped_column(Numeric, nullable=False)
    volume: Mapped[float] = mapped_column(Numeric, nullable=False)
    quote_volume: Mapped[float | None] = mapped_column(Numeric)
    trade_count: Mapped[int | None] = mapped_column(Integer)
    taker_buy_base_volume: Mapped[float | None] = mapped_column(Numeric)
    taker_buy_quote_volume: Mapped[float | None] = mapped_column(Numeric)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IndicatorSnapshot(Base):
    __tablename__ = "indicator_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "interval", "open_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    open_time: Mapped[int] = mapped_column(nullable=False)
    ema50: Mapped[float | None] = mapped_column(Numeric)
    ema200: Mapped[float | None] = mapped_column(Numeric)
    adx: Mapped[float | None] = mapped_column(Numeric)
    di_plus: Mapped[float | None] = mapped_column(Numeric)
    di_minus: Mapped[float | None] = mapped_column(Numeric)
    atr: Mapped[float | None] = mapped_column(Numeric)
    atr_pct: Mapped[float | None] = mapped_column(Numeric)
    bb_upper: Mapped[float | None] = mapped_column(Numeric)
    bb_middle: Mapped[float | None] = mapped_column(Numeric)
    bb_lower: Mapped[float | None] = mapped_column(Numeric)
    bb_width_pct: Mapped[float | None] = mapped_column(Numeric)
    volume_ma20: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

