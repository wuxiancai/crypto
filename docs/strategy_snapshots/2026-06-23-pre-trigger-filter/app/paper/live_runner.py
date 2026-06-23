from collections.abc import AsyncIterable
import asyncio
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
import time
from typing import Any

from app.data.binance import fetch_klines
from app.data.quality import Kline
from app.paper.binance_stream import (
    TickerPrice,
    iter_binance_multi_interval_websocket_klines,
    iter_binance_websocket_ticker_prices,
)
from app.paper.multitimeframe import MultiTimeframeKlineCache
from app.paper.persistence import load_paper_snapshot
from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal
from app.paper.stream import SignalFn, run_persistent_paper_kline_stream
from app.paper.trading import PaperConfig, PaperSnapshot
from app.strategy.signal_router import StrategySignal


@dataclass(frozen=True)
class RealMarketPaperConfig:
    symbols: tuple[str, ...]
    intervals: tuple[str, ...]
    websocket_base_url: str
    state_path: Path
    initial_equity: Decimal
    risk_per_trade_pct: Decimal
    maker_fee_rate: Decimal = Decimal("0.0002")
    taker_fee_rate: Decimal = Decimal("0.0005")
    slippage_pct: Decimal = Decimal("0.0005")
    leverage: Decimal = Decimal("10")
    funding_rate: Decimal = Decimal("0")
    funding_interval_ms: int = 8 * 60 * 60 * 1000
    trend_pullback_take_profit_mode: str = "TRAILING"
    strategy_config: RealtimeStrategyConfig = field(default_factory=RealtimeStrategyConfig)
    historical_warmup_enabled: bool = True
    historical_warmup_limit: int = 250


async def run_real_market_paper(
    config: RealMarketPaperConfig,
    source: AsyncIterable[Kline] | None = None,
    signal_fn: SignalFn | None = None,
    warmup_klines: list[Kline] | None = None,
) -> PaperSnapshot:
    kline_source = source or iter_binance_multi_interval_websocket_klines(
        base_url=config.websocket_base_url,
        symbols=list(config.symbols),
        intervals=list(config.intervals),
        reconnect=True,
    )
    historical_klines = warmup_klines
    if historical_klines is None and source is None and config.historical_warmup_enabled:
        historical_klines = await fetch_realtime_warmup_klines(config)
    catchup_klines = (
        _missing_klines_since_last_update(config.state_path, historical_klines or [])
        if source is None
        else []
    )
    if catchup_klines:
        kline_source = _chain_klines(catchup_klines, kline_source)
    price_task = (
        asyncio.create_task(run_realtime_price_updates(config))
        if source is None
        else None
    )
    try:
        return await run_persistent_paper_kline_stream(
            config=PaperConfig(
                initial_equity=config.initial_equity,
                risk_per_trade_pct=config.risk_per_trade_pct,
                maker_fee_rate=config.maker_fee_rate,
                taker_fee_rate=config.taker_fee_rate,
                slippage_pct=config.slippage_pct,
                leverage=config.leverage,
                funding_rate=config.funding_rate,
                funding_interval_ms=config.funding_interval_ms,
                trend_pullback_take_profit_mode=config.trend_pullback_take_profit_mode,
            ),
            source=kline_source,
            signal_fn=signal_fn
            or build_default_realtime_signal_fn(
                config.strategy_config,
                warmup_klines=historical_klines or [],
            ),
            state_path=config.state_path,
        )
    finally:
        if price_task is not None:
            price_task.cancel()
            try:
                await price_task
            except asyncio.CancelledError:
                pass


async def run_realtime_price_updates(
    config: RealMarketPaperConfig,
    source: AsyncIterable[TickerPrice] | None = None,
) -> None:
    price_source = source or iter_binance_websocket_ticker_prices(
        base_url=config.websocket_base_url,
        symbols=list(config.symbols),
        reconnect=True,
    )
    async for price in price_source:
        save_realtime_market_price(
            state_path=config.state_path,
            price=price,
            initial_equity=config.initial_equity,
        )


def save_realtime_market_price(
    state_path: Path,
    price: TickerPrice,
    initial_equity: Decimal,
) -> None:
    payload = _read_state_payload_for_market_price(state_path, initial_equity)
    market_prices = payload.get("market_prices")
    if not isinstance(market_prices, dict):
        market_prices = {}
    market_prices[price.symbol] = {
        "price": str(price.price),
        "event_time_ms": price.event_time_ms,
        "updated_at_ms": int(time.time() * 1000),
        "source": "binance_ticker_ws",
    }
    payload["market_prices"] = market_prices
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_state_payload_for_market_price(state_path: Path, initial_equity: Decimal) -> dict[str, Any]:
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            return payload
    return {
        "equity": str(initial_equity),
        "open_position": None,
        "fills": [],
        "rejected_signals": 0,
        "runtime_started_at_ms": int(time.time() * 1000),
        "last_update_at_ms": None,
        "signal_evaluations": [],
    }


async def fetch_realtime_warmup_klines(config: RealMarketPaperConfig) -> list[Kline]:
    limit = max(config.historical_warmup_limit, _required_history_limit(config.strategy_config))
    now_ms = int(time.time() * 1000)
    warmup: list[Kline] = []
    for symbol in config.symbols:
        for interval in dict.fromkeys((*config.strategy_config.trend_intervals, config.strategy_config.entry_interval)):
            try:
                klines = await fetch_klines(symbol=symbol, interval=interval, limit=limit)
            except Exception as exc:
                print(f"Historical warmup skipped for {symbol} {interval}: {exc}")
                continue
            warmup.extend(kline for kline in klines if kline.close_time < now_ms)
    return sorted(warmup, key=lambda kline: (kline.symbol, kline.interval, kline.open_time))


def build_default_realtime_signal_fn(
    config: RealtimeStrategyConfig,
    warmup_klines: list[Kline] | tuple[Kline, ...] = (),
) -> SignalFn:
    max_history = _required_history_limit(config)
    cache = MultiTimeframeKlineCache(
        required_intervals=dict.fromkeys((*config.trend_intervals, config.entry_interval)).keys(),
        max_klines_per_interval=max_history,
    )
    for kline in warmup_klines:
        cache.update(kline)

    def signal_fn(kline: Kline, has_position: bool):
        frame = cache.update(kline)
        if frame is None:
            return StrategySignal(
                action="WAIT",
                strategy_type="SYSTEM",
                reason=["waiting for required realtime timeframes"],
            )
        if kline.interval != config.entry_interval:
            return StrategySignal(
                action="WAIT",
                strategy_type="SYSTEM",
                reason=["non-entry interval observed"],
            )
        if has_position:
            return StrategySignal(
                action="WAIT",
                strategy_type="SYSTEM",
                reason=["paper position already open"],
            )
        return build_realtime_strategy_signal(frame, config=config)

    return signal_fn


async def _chain_klines(
    first: list[Kline],
    second: AsyncIterable[Kline],
) -> AsyncIterable[Kline]:
    for kline in first:
        yield kline
    async for kline in second:
        yield kline


def _missing_klines_since_last_update(state_path: Path, historical_klines: list[Kline]) -> list[Kline]:
    snapshot = load_paper_snapshot(state_path)
    if snapshot is None or snapshot.last_update_at_ms is None:
        return []
    return [
        kline
        for kline in sorted(historical_klines, key=lambda item: item.close_time)
        if kline.close_time > snapshot.last_update_at_ms
    ]


def _required_history_limit(config: RealtimeStrategyConfig) -> int:
    return max(
        config.ema_fast_period,
        config.ema_slow_period,
        config.atr_period,
        config.dmi_period,
        config.swing_lookback,
        2,
    )


def wait_signal(kline: Kline, has_position: bool) -> StrategySignal:
    return StrategySignal(
        action="WAIT",
        strategy_type="SYSTEM",
        reason=["real-market paper runner strategy not connected"],
    )
