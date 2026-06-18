from collections.abc import AsyncIterable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
import time

from app.data.binance import BinanceDataError, fetch_klines
from app.data.quality import Kline
from app.paper.binance_stream import iter_binance_multi_interval_websocket_klines
from app.paper.multitimeframe import MultiTimeframeKlineCache
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
    maker_fee_rate: Decimal
    taker_fee_rate: Decimal
    slippage_pct: Decimal
    strategy_config: RealtimeStrategyConfig = field(default_factory=RealtimeStrategyConfig)
    historical_warmup_enabled: bool = True


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
    )
    historical_klines = warmup_klines
    if historical_klines is None and source is None and config.historical_warmup_enabled:
        historical_klines = await fetch_realtime_warmup_klines(config)
    return await run_persistent_paper_kline_stream(
        config=PaperConfig(
            initial_equity=config.initial_equity,
            risk_per_trade_pct=config.risk_per_trade_pct,
            maker_fee_rate=config.maker_fee_rate,
            taker_fee_rate=config.taker_fee_rate,
            slippage_pct=config.slippage_pct,
        ),
        source=kline_source,
        signal_fn=signal_fn
        or build_default_realtime_signal_fn(
            config.strategy_config,
            warmup_klines=historical_klines or [],
        ),
        state_path=config.state_path,
    )


async def fetch_realtime_warmup_klines(config: RealMarketPaperConfig) -> list[Kline]:
    limit = _required_history_limit(config.strategy_config)
    now_ms = int(time.time() * 1000)
    warmup: list[Kline] = []
    for symbol in config.symbols:
        for interval in dict.fromkeys((*config.strategy_config.trend_intervals, config.strategy_config.entry_interval)):
            try:
                klines = await fetch_klines(symbol=symbol, interval=interval, limit=limit)
            except BinanceDataError as exc:
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
        if has_position:
            return StrategySignal(
                action="WAIT",
                strategy_type="SYSTEM",
                reason=["paper position already open"],
            )
        return build_realtime_strategy_signal(frame, config=config)

    return signal_fn


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
