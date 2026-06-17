from collections.abc import AsyncIterable, Callable
from pathlib import Path

from app.data.quality import Kline
from app.paper.persistence import load_paper_snapshot, save_paper_snapshot
from app.paper.trading import PaperConfig, PaperSnapshot, PaperTradingEngine, SignalLike


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


async def run_persistent_paper_kline_stream(
    config: PaperConfig,
    source: AsyncIterable[Kline],
    signal_fn: SignalFn,
    state_path: Path,
) -> PaperSnapshot:
    restored_snapshot = load_paper_snapshot(state_path)
    engine = (
        PaperTradingEngine.from_snapshot(config, restored_snapshot)
        if restored_snapshot is not None
        else PaperTradingEngine(config)
    )
    async for kline in source:
        engine.on_kline(kline)
        snapshot = engine.snapshot()
        signal = signal_fn(kline, snapshot.open_position is not None)
        engine.on_signal(kline=kline, signal=signal)
        save_paper_snapshot(engine.snapshot(), state_path)
    return engine.snapshot()
