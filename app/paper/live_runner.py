from collections.abc import AsyncIterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.data.quality import Kline
from app.paper.binance_stream import iter_binance_websocket_klines
from app.paper.stream import SignalFn, run_persistent_paper_kline_stream
from app.paper.trading import PaperConfig, PaperSnapshot
from app.strategy.signal_router import StrategySignal


@dataclass(frozen=True)
class RealMarketPaperConfig:
    symbols: tuple[str, ...]
    interval: str
    websocket_base_url: str
    state_path: Path
    initial_equity: Decimal
    risk_per_trade_pct: Decimal
    maker_fee_rate: Decimal
    taker_fee_rate: Decimal
    slippage_pct: Decimal


async def run_real_market_paper(
    config: RealMarketPaperConfig,
    source: AsyncIterable[Kline] | None = None,
    signal_fn: SignalFn = None,
) -> PaperSnapshot:
    kline_source = source or iter_binance_websocket_klines(
        base_url=config.websocket_base_url,
        symbols=list(config.symbols),
        interval=config.interval,
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
        signal_fn=signal_fn or wait_signal,
        state_path=config.state_path,
    )


def wait_signal(kline: Kline, has_position: bool) -> StrategySignal:
    return StrategySignal(
        action="WAIT",
        strategy_type="SYSTEM",
        reason=["real-market paper runner strategy not connected"],
    )
