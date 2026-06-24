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
from app.paper.persistence import _fill_to_payload, _position_to_payload, load_paper_snapshot
from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal
from app.paper.stream import PaperStreamEvent, PaperStreamEventSink, SignalFn, run_persistent_paper_kline_stream
from app.paper.trading import PaperConfig, PaperSnapshot
from app.strategy.signal_router import StrategySignal


_CHART_DISPLAY_POINTS = 80


def default_paper_strategy_config() -> RealtimeStrategyConfig:
    return RealtimeStrategyConfig(
        fast_ma_type="EMA",
        slow_ma_type="MA",
        ema_fast_period=15,
        ema_slow_period=60,
        atr_period=14,
        dmi_period=12,
        swing_lookback=20,
        pullback_zone_atr_multiplier=Decimal("1"),
        require_pullback_close_beyond_fast_ma=False,
        enable_reversal_probe=False,
        enable_layered_strategy=True,
    )


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
    max_fee_to_risk_ratio: Decimal | None = Decimal("0")
    trend_pullback_take_profit_mode: str = "TRAILING"
    strategy_config: RealtimeStrategyConfig = field(default_factory=default_paper_strategy_config)
    historical_warmup_enabled: bool = True
    historical_warmup_limit: int = 250
    event_session_factory: Any | None = None


async def run_real_market_paper(
    config: RealMarketPaperConfig,
    source: AsyncIterable[Kline] | None = None,
    signal_fn: SignalFn | None = None,
    warmup_klines: list[Kline] | None = None,
) -> PaperSnapshot:
    save_paper_strategy_details(config)
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
                max_fee_to_risk_ratio=config.max_fee_to_risk_ratio,
            ),
            source=kline_source,
            signal_fn=signal_fn
            or build_default_realtime_signal_fn(
                config.strategy_config,
                warmup_klines=historical_klines or [],
            ),
            state_path=config.state_path,
            event_sink=_paper_runtime_event_sink(config.event_session_factory),
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
        for interval in _required_strategy_intervals(config.strategy_config):
            try:
                klines = await fetch_klines(symbol=symbol, interval=interval, limit=limit)
            except Exception as exc:
                print(f"Historical warmup skipped for {symbol} {interval}: {exc}")
                continue
            warmup.extend(kline for kline in klines if kline.close_time < now_ms)
    return sorted(warmup, key=lambda kline: (kline.symbol, kline.interval, kline.open_time))


def save_paper_strategy_details(config: RealMarketPaperConfig) -> None:
    payload = _read_state_payload_for_market_price(config.state_path, config.initial_equity)
    payload["strategy_details"] = [
        _strategy_detail_payload(symbol=symbol, config=config)
        for symbol in config.symbols
    ]
    config.state_path.parent.mkdir(parents=True, exist_ok=True)
    config.state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _strategy_detail_payload(symbol: str, config: RealMarketPaperConfig) -> dict[str, str | bool]:
    strategy_config = config.strategy_config
    return {
        "symbol": symbol,
        "fast_ma": f"{strategy_config.fast_ma_type.upper()}{strategy_config.ema_fast_period}",
        "slow_ma": f"{strategy_config.slow_ma_type.upper()}{strategy_config.ema_slow_period}",
        "atr_period": str(strategy_config.atr_period),
        "dmi_period": str(strategy_config.dmi_period),
        "swing_lookback": str(strategy_config.swing_lookback),
        "max_fee_to_risk_ratio": "0"
        if config.max_fee_to_risk_ratio is None
        else str(config.max_fee_to_risk_ratio),
        "trend_pullback_take_profit_mode": config.trend_pullback_take_profit_mode,
        "pullback_zone_atr_multiplier": str(strategy_config.pullback_zone_atr_multiplier),
        "require_pullback_close_beyond_fast_ma": strategy_config.require_pullback_close_beyond_fast_ma,
        "enable_reversal_probe": strategy_config.enable_reversal_probe,
    }


def build_default_realtime_signal_fn(
    config: RealtimeStrategyConfig,
    warmup_klines: list[Kline] | tuple[Kline, ...] = (),
) -> SignalFn:
    max_history = _required_history_limit(config)
    cache = MultiTimeframeKlineCache(
        required_intervals=_required_strategy_intervals(config),
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
        config.ema_slow_period + _CHART_DISPLAY_POINTS - 1,
        config.atr_period,
        config.dmi_period,
        config.swing_lookback,
        2,
    )


def _required_strategy_intervals(config: RealtimeStrategyConfig) -> tuple[str, ...]:
    intervals = (
        (config.main_trend_interval,) if config.enable_layered_strategy else ()
    ) + (*config.trend_intervals, config.entry_interval)
    return tuple(
        dict.fromkeys(intervals)
    )


def wait_signal(kline: Kline, has_position: bool) -> StrategySignal:
    return StrategySignal(
        action="WAIT",
        strategy_type="SYSTEM",
        reason=["real-market paper runner strategy not connected"],
    )


def _paper_runtime_event_sink(session_factory: Any | None) -> PaperStreamEventSink | None:
    if session_factory is None:
        return None

    def sink(event: PaperStreamEvent) -> None:
        try:
            from app.database.repositories import record_paper_runtime_event

            with session_factory() as session:
                for payload in _paper_runtime_event_payloads(event):
                    record_paper_runtime_event(session, **payload)
        except Exception as exc:
            print(f"Paper runtime event persistence skipped: {exc}")

    return sink


def _paper_runtime_event_payloads(event: PaperStreamEvent) -> list[dict[str, object]]:
    payloads = [
        _paper_runtime_event_payload(
            event_type="signal",
            event=event,
            strategy_type=str(event.signal.strategy_type),
            action=str(event.signal.action),
            bucket=getattr(event.signal, "bucket", None),
            payload=_signal_payload(event),
        ),
        _paper_runtime_event_payload(
            event_type="snapshot",
            event=event,
            strategy_type="SYSTEM",
            action="SNAPSHOT",
            bucket=None,
            payload=_snapshot_payload(event),
        ),
    ]
    if event.rejected_signal:
        payloads.append(
            _paper_runtime_event_payload(
                event_type="rejected_signal",
                event=event,
                strategy_type=str(event.signal.strategy_type),
                action=str(event.signal.action),
                bucket=getattr(event.signal, "bucket", None),
                payload=_signal_payload(event),
            )
        )
    if event.closed_fill is not None:
        payloads.append(
            _paper_runtime_event_payload(
                event_type="fill",
                event=event,
                strategy_type=event.closed_fill.strategy_type,
                action="EXIT",
                bucket=event.closed_fill.bucket,
                payload=_fill_to_payload(event.closed_fill),
            )
        )
    return payloads


def _paper_runtime_event_payload(
    *,
    event_type: str,
    event: PaperStreamEvent,
    strategy_type: str,
    action: str,
    bucket: str | None,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "symbol": event.kline.symbol,
        "interval": event.kline.interval,
        "event_time": int(event.kline.close_time),
        "strategy_type": strategy_type,
        "action": action,
        "bucket": bucket,
        "payload": payload,
    }


def _signal_payload(event: PaperStreamEvent) -> dict[str, object]:
    signal = event.signal
    return {
        "kline": {
            "open_time": event.kline.open_time,
            "close_time": event.kline.close_time,
            "close": str(event.kline.close),
        },
        "action": str(signal.action),
        "strategy_type": str(signal.strategy_type),
        "bucket": getattr(signal, "bucket", None),
        "reason": list(getattr(signal, "reason", []) or []),
        "core_rules": list(getattr(signal, "core_rules", []) or []),
        "condition_statuses": list(getattr(signal, "condition_statuses", []) or []),
        "opened_position": _position_to_payload(event.opened_position),
        "rejected_signal": event.rejected_signal,
    }


def _snapshot_payload(event: PaperStreamEvent) -> dict[str, object]:
    return {
        "equity": str(event.snapshot.equity),
        "open_positions": [
            _position_to_payload(position)
            for position in event.snapshot.open_positions
        ],
        "rejected_signals": event.snapshot.rejected_signals,
        "last_update_at_ms": event.snapshot.last_update_at_ms,
        "fills_count": len(event.snapshot.fills),
    }
