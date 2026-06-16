from collections.abc import AsyncIterable, Callable

from app.data.quality import Kline
from app.paper.trading import PaperSnapshot, PaperTradingEngine, SignalLike


SignalFn = Callable[[Kline, bool], SignalLike]


async def run_paper_kline_stream(
    engine: PaperTradingEngine,
    source: AsyncIterable[Kline],
    signal_fn: SignalFn,
) -> PaperSnapshot:
    async for kline in source:
        engine.on_kline(kline)
        snapshot = engine.snapshot()
        signal = signal_fn(kline, snapshot.open_position is not None)
        engine.on_signal(kline=kline, signal=signal)
    return engine.snapshot()
