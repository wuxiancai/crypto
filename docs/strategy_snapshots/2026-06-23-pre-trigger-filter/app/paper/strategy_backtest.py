from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import time

from app.data.binance import BinanceDataError, fetch_klines
from app.data.quality import INTERVAL_MS, Kline
from app.paper.live_runner import build_default_realtime_signal_fn
from app.paper.persistence import _fill_to_payload
from app.paper.strategy_adapter import RealtimeStrategyConfig
from app.paper.trading import PaperConfig, PaperTradingEngine


@dataclass(frozen=True)
class StrategyBacktestConfig:
    symbols: tuple[str, ...] = ("BTCUSDT",)
    fast_ma_type: str = "EMA"
    slow_ma_type: str = "EMA"
    ema_fast_period: int = 50
    ema_slow_period: int = 200
    atr_period: int = 14
    dmi_period: int = 14
    swing_lookback: int = 20
    limit: int = 1500
    history_period: str = "3m"
    history_start_time_ms: int | None = None
    history_end_time_ms: int | None = None
    history_cache_dir: Path | None = Path("runtime/backtest-klines")
    initial_equity: Decimal = Decimal("1000")
    risk_per_trade_pct: Decimal = Decimal("0.005")
    maker_fee_rate: Decimal = Decimal("0.0002")
    taker_fee_rate: Decimal = Decimal("0.0005")
    slippage_pct: Decimal = Decimal("0")
    leverage: Decimal = Decimal("10")
    funding_rate: Decimal = Decimal("0")
    funding_interval_ms: int = 8 * 60 * 60 * 1000
    trend_pullback_take_profit_mode: str = "TRAILING"
    max_fee_to_risk_ratio: Decimal | None = Decimal("0.25")


@dataclass(frozen=True)
class StrategyBacktestResult:
    config: StrategyBacktestConfig
    initial_equity: str
    final_equity: str
    total_trades: int
    wins: int
    losses: int
    net_pnl: str
    trades: list[dict[str, str]]
    error: str | None = None


@dataclass(frozen=True)
class StrategyBacktestRunSummary:
    created_at: datetime
    symbol: str
    fast_ma_type: str
    fast_period: int
    slow_ma_type: str
    slow_period: int
    atr_period: int
    dmi_period: int
    swing_lookback: int
    max_fee_to_risk_ratio: str
    history_period: str
    initial_equity: str
    final_equity: str
    total_trades: int
    wins: int
    losses: int
    net_pnl: str


async def run_strategy_backtest(config: StrategyBacktestConfig | None = None) -> StrategyBacktestResult:
    backtest_config = config or StrategyBacktestConfig()
    try:
        historical_klines = await _fetch_backtest_klines(backtest_config)
    except BinanceDataError as exc:
        return _empty_result(backtest_config, error=str(exc))

    strategy_config = RealtimeStrategyConfig(
        fast_ma_type=backtest_config.fast_ma_type,
        slow_ma_type=backtest_config.slow_ma_type,
        ema_fast_period=backtest_config.ema_fast_period,
        ema_slow_period=backtest_config.ema_slow_period,
        atr_period=backtest_config.atr_period,
        dmi_period=backtest_config.dmi_period,
        swing_lookback=backtest_config.swing_lookback,
    )
    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=backtest_config.initial_equity,
            risk_per_trade_pct=backtest_config.risk_per_trade_pct,
            maker_fee_rate=backtest_config.maker_fee_rate,
            taker_fee_rate=backtest_config.taker_fee_rate,
            slippage_pct=backtest_config.slippage_pct,
            leverage=backtest_config.leverage,
            funding_rate=backtest_config.funding_rate,
            funding_interval_ms=backtest_config.funding_interval_ms,
            trend_pullback_take_profit_mode=backtest_config.trend_pullback_take_profit_mode,
            max_fee_to_risk_ratio=backtest_config.max_fee_to_risk_ratio,
        )
    )
    signal_fn = build_default_realtime_signal_fn(strategy_config, warmup_klines=())

    for kline in historical_klines:
        closed_fill = engine.on_kline(kline)
        if closed_fill is not None:
            continue
        snapshot = engine.snapshot()
        signal = signal_fn(kline, snapshot.open_position is not None)
        engine.on_signal(kline=kline, signal=signal)

    snapshot = engine.snapshot()
    trades = [_normalise_trade(_fill_to_payload(fill)) for fill in reversed(snapshot.fills)]
    wins = sum(1 for fill in snapshot.fills if fill.net_pnl > 0)
    losses = sum(1 for fill in snapshot.fills if fill.net_pnl < 0)
    net_pnl = snapshot.equity - backtest_config.initial_equity
    return StrategyBacktestResult(
        config=backtest_config,
        initial_equity=_money(backtest_config.initial_equity),
        final_equity=_money(snapshot.equity),
        total_trades=len(snapshot.fills),
        wins=wins,
        losses=losses,
        net_pnl=_money(net_pnl),
        trades=trades,
        error=None,
    )


async def _fetch_backtest_klines(config: StrategyBacktestConfig) -> list[Kline]:
    intervals = ("4h", "1h", "15m")
    end_time = config.history_end_time_ms or int(time.time() * 1000)
    start_time = config.history_start_time_ms
    if start_time is None:
        start_time = end_time - _history_window_ms(config.history_period)
    historical: list[Kline] = []
    for symbol in config.symbols:
        for interval in intervals:
            historical.extend(
                await _fetch_interval_pages(
                    symbol,
                    interval,
                    config.limit,
                    start_time,
                    end_time,
                    config.history_cache_dir,
                )
            )
    return sorted(historical, key=lambda kline: (kline.open_time, kline.symbol, kline.interval))


async def _fetch_interval_pages(
    symbol: str,
    interval: str,
    limit: int,
    start_time: int,
    end_time: int,
    cache_dir: Path | None = Path("runtime/backtest-klines"),
) -> list[Kline]:
    cached = _read_cached_klines(cache_dir, symbol, interval)
    missing_ranges = _missing_kline_ranges(cached, interval, start_time, end_time)
    fetched: list[Kline] = []
    for missing_start, missing_end in missing_ranges:
        fetched.extend(
            await _fetch_interval_pages_from_binance(
                symbol=symbol,
                interval=interval,
                limit=limit,
                start_time=missing_start,
                end_time=missing_end,
            )
        )
    if fetched:
        cached = _write_cached_klines(cache_dir, symbol, interval, [*cached, *fetched])
    return [
        kline
        for kline in sorted(cached, key=lambda item: item.open_time)
        if start_time <= kline.open_time <= end_time
    ]


async def _fetch_interval_pages_from_binance(
    symbol: str,
    interval: str,
    limit: int,
    start_time: int,
    end_time: int,
) -> list[Kline]:
    page_limit = max(1, min(1500, limit))
    cursor = start_time
    pages: list[Kline] = []
    interval_ms = INTERVAL_MS[interval]
    while cursor <= end_time:
        page_end = min(end_time, cursor + interval_ms * page_limit - 1)
        page = await fetch_klines(
            symbol=symbol,
            interval=interval,
            limit=page_limit,
            start_time=cursor,
            end_time=page_end,
        )
        pages.extend(page)
        if not page:
            cursor = page_end + 1
            continue
        next_cursor = max(kline.open_time for kline in page) + interval_ms
        cursor = max(next_cursor, page_end + 1)
    return pages


def _read_cached_klines(cache_dir: Path | None, symbol: str, interval: str) -> list[Kline]:
    if cache_dir is None:
        return []
    path = _cache_path(cache_dir, symbol, interval)
    if not path.exists():
        return []
    rows: list[Kline] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = Kline.model_validate(json.loads(line))
        if row.symbol == symbol and row.interval == interval and row.is_closed:
            rows.append(row)
    return sorted(rows, key=lambda item: item.open_time)


def _write_cached_klines(cache_dir: Path | None, symbol: str, interval: str, rows: list[Kline]) -> list[Kline]:
    filtered = {
        row.open_time: row
        for row in rows
        if row.symbol == symbol and row.interval == interval and row.is_closed
    }
    merged = [filtered[key] for key in sorted(filtered)]
    if cache_dir is None:
        return merged
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, symbol, interval)
    payload = "\n".join(json.dumps(row.model_dump(mode="json"), sort_keys=True) for row in merged)
    path.write_text(f"{payload}\n" if payload else "", encoding="utf-8")
    return merged


def _missing_kline_ranges(
    cached: list[Kline],
    interval: str,
    start_time: int,
    end_time: int,
) -> list[tuple[int, int]]:
    interval_ms = INTERVAL_MS[interval]
    first_open = _ceil_to_interval(start_time, interval_ms)
    last_open = (end_time // interval_ms) * interval_ms
    if first_open > last_open:
        return []

    cached_open_times = {
        kline.open_time
        for kline in cached
        if start_time <= kline.open_time <= end_time
    }
    ranges: list[tuple[int, int]] = []
    missing_start: int | None = None
    cursor = first_open
    while cursor <= last_open:
        if cursor not in cached_open_times and missing_start is None:
            missing_start = cursor
        if cursor in cached_open_times and missing_start is not None:
            ranges.append((missing_start, cursor - 1))
            missing_start = None
        cursor += interval_ms
    if missing_start is not None:
        ranges.append((missing_start, min(end_time, last_open + interval_ms - 1)))
    return ranges


def _ceil_to_interval(value: int, interval_ms: int) -> int:
    return ((value + interval_ms - 1) // interval_ms) * interval_ms


def _cache_path(cache_dir: Path, symbol: str, interval: str) -> Path:
    return cache_dir / f"{symbol}-{interval}.jsonl"


def _history_window_ms(period: str) -> int:
    days_by_period = {
        "3m": 90,
        "6m": 180,
        "1y": 365,
        "2y": 730,
    }
    days = days_by_period.get(period, 90)
    return days * 24 * 60 * 60 * 1000


def _empty_result(config: StrategyBacktestConfig, error: str | None = None) -> StrategyBacktestResult:
    return StrategyBacktestResult(
        config=config,
        initial_equity=_money(config.initial_equity),
        final_equity=_money(config.initial_equity),
        total_trades=0,
        wins=0,
        losses=0,
        net_pnl=_money(Decimal("0")),
        trades=[],
        error=error,
    )


def _normalise_trade(trade: dict[str, object]) -> dict[str, str]:
    return {key: str(value) for key, value in trade.items()}


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")
