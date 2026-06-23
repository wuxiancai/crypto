import hashlib
import json
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.backtest.engine import BacktestResult
from app.data.quality import Kline
from app.database.models import BacktestRun, BacktestTradeRecord, ConfigSnapshot, KlineRecord
from app.paper.strategy_backtest import StrategyBacktestResult, StrategyBacktestRunSummary
from app.strategy.layered_strategy import (
    DAY_CORE,
    FOUR_HOUR_ADDON,
    FOUR_HOUR_HEDGE,
    LONG_4H_1H_ADDON,
    LONG_4H_HEDGE,
    LONG_DAY_CORE,
    SHORT_4H_1H_ADDON,
    SHORT_4H_HEDGE,
    SHORT_DAY_CORE,
)


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
    config_content = json.dumps(strategy_backtest_config_payload(config), sort_keys=True)
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


def find_archived_strategy_backtest_run(
    session: Session,
    config: object,
) -> BacktestRun | None:
    content_hash = strategy_backtest_config_hash(config)
    return session.execute(
        select(BacktestRun)
        .join(ConfigSnapshot, BacktestRun.config_snapshot_id == ConfigSnapshot.id)
        .where(BacktestRun.name == "web_strategy_backtest")
        .where(ConfigSnapshot.name == "strategy_backtest")
        .where(ConfigSnapshot.content_hash == content_hash)
        .order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def strategy_backtest_config_hash(config: object) -> str:
    content = json.dumps(strategy_backtest_config_payload(config), sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def strategy_backtest_config_payload(config: object) -> dict[str, str]:
    return {
        "symbols": ",".join(getattr(config, "symbols")),
        "fast_ma_type": str(getattr(config, "fast_ma_type")),
        "slow_ma_type": str(getattr(config, "slow_ma_type")),
        "ema_fast_period": str(getattr(config, "ema_fast_period")),
        "ema_slow_period": str(getattr(config, "ema_slow_period")),
        "atr_period": str(getattr(config, "atr_period")),
        "dmi_period": str(getattr(config, "dmi_period")),
        "swing_lookback": str(getattr(config, "swing_lookback")),
        "limit": str(getattr(config, "limit")),
        "history_period": str(getattr(config, "history_period")),
        "initial_equity": str(getattr(config, "initial_equity")),
        "risk_per_trade_pct": str(getattr(config, "risk_per_trade_pct")),
        "maker_fee_rate": str(getattr(config, "maker_fee_rate")),
        "taker_fee_rate": str(getattr(config, "taker_fee_rate")),
        "leverage": str(getattr(config, "leverage")),
        "trend_pullback_take_profit_mode": str(getattr(config, "trend_pullback_take_profit_mode")),
        "max_fee_to_risk_ratio": str(getattr(config, "max_fee_to_risk_ratio")),
        "pullback_zone_atr_multiplier": str(getattr(config, "pullback_zone_atr_multiplier", "1")),
        "require_pullback_close_beyond_fast_ma": str(
            getattr(config, "require_pullback_close_beyond_fast_ma", False)
        ),
        "enable_reversal_probe": str(getattr(config, "enable_reversal_probe", True)),
    }


def list_strategy_backtest_summaries(
    session: Session,
    limit: int = 100,
) -> list[StrategyBacktestRunSummary]:
    rows = session.execute(
        select(BacktestRun, ConfigSnapshot)
        .join(ConfigSnapshot, BacktestRun.config_snapshot_id == ConfigSnapshot.id)
        .where(BacktestRun.name == "web_strategy_backtest")
        .where(ConfigSnapshot.name == "strategy_backtest")
        .order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
        .limit(max(1, limit))
    ).all()
    run_ids = [int(run.id) for run, _snapshot in rows]
    trades_by_run: dict[int, list[BacktestTradeRecord]] = {run_id: [] for run_id in run_ids}
    if run_ids:
        trades = session.execute(
            select(BacktestTradeRecord)
            .where(BacktestTradeRecord.backtest_run_id.in_(run_ids))
            .order_by(BacktestTradeRecord.exit_time.asc(), BacktestTradeRecord.id.asc())
        ).scalars().all()
        for trade in trades:
            trades_by_run.setdefault(int(trade.backtest_run_id), []).append(trade)
    return [
        _strategy_backtest_summary(run, snapshot, trades_by_run.get(int(run.id), []))
        for run, snapshot in rows
    ]


def clear_strategy_backtest_history(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(BacktestRun.id, BacktestRun.config_snapshot_id)
        .join(ConfigSnapshot, BacktestRun.config_snapshot_id == ConfigSnapshot.id)
        .where(BacktestRun.name == "web_strategy_backtest")
        .where(ConfigSnapshot.name == "strategy_backtest")
    ).all()
    run_ids = [int(row.id) for row in rows]
    config_snapshot_ids = {int(row.config_snapshot_id) for row in rows}
    if not run_ids:
        return {"runs": 0, "trades": 0, "config_snapshots": 0}

    trades_deleted = session.execute(
        delete(BacktestTradeRecord).where(BacktestTradeRecord.backtest_run_id.in_(run_ids))
    ).rowcount or 0
    runs_deleted = session.execute(
        delete(BacktestRun).where(BacktestRun.id.in_(run_ids))
    ).rowcount or 0

    configs_deleted = 0
    for config_snapshot_id in config_snapshot_ids:
        still_used = session.execute(
            select(BacktestRun.id)
            .where(BacktestRun.config_snapshot_id == config_snapshot_id)
            .limit(1)
        ).first()
        if still_used is None:
            configs_deleted += session.execute(
                delete(ConfigSnapshot).where(ConfigSnapshot.id == config_snapshot_id)
            ).rowcount or 0

    session.commit()
    return {
        "runs": runs_deleted,
        "trades": trades_deleted,
        "config_snapshots": configs_deleted,
    }


def _strategy_backtest_summary(
    run: BacktestRun,
    snapshot: ConfigSnapshot,
    trades: list[BacktestTradeRecord] | None = None,
) -> StrategyBacktestRunSummary:
    payload = _decode_config_content(snapshot.content)
    symbols = str(payload.get("symbols") or "UNKNOWN")
    symbol = symbols.split(",", 1)[0] if symbols else "UNKNOWN"
    max_drawdown, max_drawdown_pct = _summary_drawdown_metrics(Decimal(str(run.initial_equity)), trades or [])
    return StrategyBacktestRunSummary(
        created_at=run.created_at,
        symbol=symbol,
        fast_ma_type=_average_type_from_payload(payload, "fast_ma_type"),
        fast_period=_int_from_payload(payload, "ema_fast_period", 50),
        slow_ma_type=_average_type_from_payload(payload, "slow_ma_type"),
        slow_period=_int_from_payload(payload, "ema_slow_period", 200),
        atr_period=_int_from_payload(payload, "atr_period", 14),
        dmi_period=_int_from_payload(payload, "dmi_period", 14),
        swing_lookback=_int_from_payload(payload, "swing_lookback", 20),
        max_fee_to_risk_ratio=str(payload.get("max_fee_to_risk_ratio") or "0.25"),
        history_period=str(payload.get("history_period") or "unknown"),
        initial_equity=_money_string(run.initial_equity),
        final_equity=_money_string(run.final_equity),
        total_trades=run.total_trades,
        wins=run.wins,
        losses=run.losses,
        net_pnl=_money_string(run.net_pnl),
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        profit_loss_ratio=_summary_profit_loss_ratio(trades or []),
        bucket_metrics=_summary_bucket_metrics(trades or []),
    )


def _summary_drawdown_metrics(
    initial_equity: Decimal,
    trades: list[BacktestTradeRecord],
) -> tuple[str, str]:
    peak = initial_equity
    equity = initial_equity
    max_drawdown = Decimal("0")
    for trade in sorted(trades, key=lambda item: (int(item.exit_time), int(item.id or 0))):
        equity += Decimal(str(trade.net_pnl))
        if equity > peak:
            peak = equity
            continue
        drawdown = peak - equity
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    pct = Decimal("0") if peak <= 0 else max_drawdown / peak * Decimal("100")
    return _money_string(max_drawdown), _decimal_string(pct)


def _summary_profit_loss_ratio(trades: list[BacktestTradeRecord]) -> str:
    wins = [Decimal(str(trade.net_pnl)) for trade in trades if Decimal(str(trade.net_pnl)) > 0]
    losses = [abs(Decimal(str(trade.net_pnl))) for trade in trades if Decimal(str(trade.net_pnl)) < 0]
    if not wins:
        return _decimal_string(Decimal("0"))
    if not losses:
        return "∞"
    average_win = sum(wins, Decimal("0")) / Decimal(len(wins))
    average_loss = sum(losses, Decimal("0")) / Decimal(len(losses))
    if average_loss == 0:
        return "∞"
    return _decimal_string(average_win / average_loss)


def _summary_bucket_metrics(trades: list[BacktestTradeRecord]) -> dict[str, dict[str, str | int]]:
    metrics: dict[str, dict[str, Decimal | int]] = {}
    for trade in trades:
        bucket = _bucket_from_strategy_type(str(trade.strategy_type))
        bucket_metrics = metrics.setdefault(
            bucket,
            {"trade_count": 0, "wins": 0, "losses": 0, "net_pnl": Decimal("0")},
        )
        net_pnl = Decimal(str(trade.net_pnl))
        bucket_metrics["trade_count"] = int(bucket_metrics["trade_count"]) + 1
        if net_pnl > 0:
            bucket_metrics["wins"] = int(bucket_metrics["wins"]) + 1
        elif net_pnl < 0:
            bucket_metrics["losses"] = int(bucket_metrics["losses"]) + 1
        bucket_metrics["net_pnl"] = Decimal(str(bucket_metrics["net_pnl"])) + net_pnl
    return {
        bucket: {
            "trade_count": int(values["trade_count"]),
            "wins": int(values["wins"]),
            "losses": int(values["losses"]),
            "net_pnl": _money_string(values["net_pnl"]),
        }
        for bucket, values in sorted(metrics.items())
    }


def _bucket_from_strategy_type(strategy_type: str) -> str:
    if strategy_type in {SHORT_DAY_CORE, LONG_DAY_CORE}:
        return DAY_CORE
    if strategy_type in {SHORT_4H_1H_ADDON, LONG_4H_1H_ADDON}:
        return FOUR_HOUR_ADDON
    if strategy_type in {LONG_4H_HEDGE, SHORT_4H_HEDGE}:
        return FOUR_HOUR_HEDGE
    return "LEGACY"


def _decode_config_content(content: str | None) -> dict[str, object]:
    if not content:
        return {}
    try:
        loaded = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _average_type_from_payload(payload: dict[str, object], key: str) -> str:
    value = str(payload.get(key) or "EMA").upper()
    return value if value in {"EMA", "MA"} else "EMA"


def _int_from_payload(payload: dict[str, object], key: str, default: int) -> int:
    try:
        return int(str(payload.get(key) or default))
    except ValueError:
        return default


def _money_string(value: object) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def _decimal_string(value: object) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")
