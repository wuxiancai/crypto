import hashlib
import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.engine import BacktestResult
from app.data.quality import Kline
from app.database.models import BacktestRun, BacktestTradeRecord, ConfigSnapshot, KlineRecord
from app.paper.strategy_backtest import StrategyBacktestResult


def upsert_klines(session: Session, rows: list[Kline]) -> int:
    written = 0
    for row in rows:
        existing = session.execute(
            select(KlineRecord).where(
                KlineRecord.symbol == row.symbol,
                KlineRecord.interval == row.interval,
                KlineRecord.open_time == row.open_time,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(_to_record(row))
        else:
            existing.close_time = row.close_time
            existing.open = row.open
            existing.high = row.high
            existing.low = row.low
            existing.close = row.close
            existing.volume = row.volume
            existing.is_closed = row.is_closed
        written += 1
    session.commit()
    return written


def _to_record(row: Kline) -> KlineRecord:
    return KlineRecord(
        symbol=row.symbol,
        interval=row.interval,
        open_time=row.open_time,
        close_time=row.close_time,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        volume=row.volume,
        is_closed=row.is_closed,
    )


def archive_backtest_result(
    session: Session,
    name: str,
    config_name: str,
    config_version: str,
    config_payload: dict[str, str],
    result: BacktestResult,
) -> int:
    config_content = json.dumps(config_payload, sort_keys=True)
    config_snapshot = ConfigSnapshot(
        name=config_name,
        version=config_version,
        content_hash=hashlib.sha256(config_content.encode("utf-8")).hexdigest(),
        content=config_content,
    )
    session.add(config_snapshot)
    session.flush()

    run = BacktestRun(
        name=name,
        config_snapshot_id=config_snapshot.id,
        initial_equity=result.initial_equity,
        final_equity=result.final_equity,
        total_trades=result.metrics.total_trades,
        wins=result.metrics.wins,
        losses=result.metrics.losses,
        net_pnl=result.metrics.net_pnl,
    )
    session.add(run)
    session.flush()

    for trade in result.trades:
        session.add(
            BacktestTradeRecord(
                backtest_run_id=run.id,
                symbol=trade.symbol,
                side=trade.side,
                strategy_type=trade.strategy_type,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                gross_pnl=trade.gross_pnl,
                fees=trade.fees,
                funding_fee=trade.funding_fee,
                net_pnl=trade.net_pnl,
                exit_reason=trade.exit_reason,
            )
        )
    session.commit()
    return run.id


def archive_strategy_backtest_result(
    session: Session,
    result: StrategyBacktestResult,
) -> int:
    config = result.config
    config_payload = {
        "symbols": ",".join(config.symbols),
        "ema_fast_period": str(config.ema_fast_period),
        "ema_slow_period": str(config.ema_slow_period),
        "atr_period": str(config.atr_period),
        "dmi_period": str(config.dmi_period),
        "swing_lookback": str(config.swing_lookback),
        "limit": str(config.limit),
        "history_period": str(config.history_period),
        "initial_equity": str(config.initial_equity),
        "risk_per_trade_pct": str(config.risk_per_trade_pct),
        "maker_fee_rate": str(config.maker_fee_rate),
        "taker_fee_rate": str(config.taker_fee_rate),
        "leverage": str(config.leverage),
        "trend_pullback_take_profit_mode": str(config.trend_pullback_take_profit_mode),
        "max_fee_to_risk_ratio": str(config.max_fee_to_risk_ratio),
    }
    config_content = json.dumps(config_payload, sort_keys=True)
    config_snapshot = ConfigSnapshot(
        name="strategy_backtest",
        version="v1",
        content_hash=hashlib.sha256(config_content.encode("utf-8")).hexdigest(),
        content=config_content,
    )
    session.add(config_snapshot)
    session.flush()

    run = BacktestRun(
        name="web_strategy_backtest",
        config_snapshot_id=config_snapshot.id,
        initial_equity=Decimal(result.initial_equity),
        final_equity=Decimal(result.final_equity),
        total_trades=result.total_trades,
        wins=result.wins,
        losses=result.losses,
        net_pnl=Decimal(result.net_pnl),
    )
    session.add(run)
    session.flush()

    for trade in result.trades:
        session.add(
            BacktestTradeRecord(
                backtest_run_id=run.id,
                symbol=str(trade.get("symbol", "")),
                side=str(trade.get("side", "")),
                strategy_type=str(trade.get("strategy_type", "")),
                entry_time=int(trade.get("entry_time", "0")),
                exit_time=int(trade.get("exit_time", "0")),
                entry_price=Decimal(trade.get("entry_price", "0")),
                exit_price=Decimal(trade.get("exit_price", "0")),
                quantity=Decimal(trade.get("quantity", "0")),
                gross_pnl=Decimal(trade.get("gross_pnl", "0")),
                fees=Decimal(trade.get("fees", "0")),
                funding_fee=Decimal(trade.get("funding_fee", "0")),
                net_pnl=Decimal(trade.get("net_pnl", "0")),
                exit_reason=str(trade.get("exit_reason", "")),
            )
        )
    session.commit()
    return run.id
