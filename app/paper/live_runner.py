from collections.abc import AsyncIterable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

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


async def run_real_market_paper(
    config: RealMarketPaperConfig,
    source: AsyncIterable[Kline] | None = None,
    signal_fn: SignalFn | None = None,
) -> PaperSnapshot:
    kline_source = source or iter_binance_multi_interval_websocket_klines(
        base_url=config.websocket_base_url,
        symbols=list(config.symbols),
        intervals=list(config.intervals),
    )
    return await run_persistent_paper_kline_stream(
        config=PaperConfig(
            initial_equity=config.initial_equity,
            risk_per_trade_pct=config.risk_per_trade_pct,
            maker_fee_rate=config.maker_fee_rate,
            taker_fee_rate=config.taker_fee_rate,
            slippage_pct=config.slippage_pct,
        ),
        source=kline_source,
        signal_fn=signal_fn or build_default_realtime_signal_fn(config.strategy_config),
        state_path=config.state_path,
    )


def build_default_realtime_signal_fn(config: RealtimeStrategyConfig) -> SignalFn:
    required_intervals = (*config.trend_intervals, config.entry_interval)
    max_history = max(
        config.ema_fast_period,
        config.ema_slow_period,
        config.atr_period,
        config.dmi_period,
        config.swing_lookback,
        2,
    )
    cache = MultiTimeframeKlineCache(
        required_intervals=dict.fromkeys(required_intervals).keys(),
        max_klines_per_interval=max_history,
    )

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


def wait_signal(kline: Kline, has_position: bool) -> StrategySignal:
    return StrategySignal(
        action="WAIT",
        strategy_type="SYSTEM",
        reason=["real-market paper runner strategy not connected"],
    )
