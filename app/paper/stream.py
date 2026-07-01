from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass, replace
import inspect
from pathlib import Path
import time

from app.data.quality import Kline
from app.paper.persistence import load_paper_snapshot, save_paper_snapshot
from app.paper.trading import (
    PaperConfig,
    PaperFill,
    PaperPosition,
    PaperSignalEvaluation,
    PaperSnapshot,
    PaperTradingEngine,
    SignalLike,
)
from app.strategy.signal_router import StrategySignal


SignalFn = Callable[..., SignalLike]
PaperStreamEventSink = Callable[["PaperStreamEvent"], None]


@dataclass(frozen=True)
class PaperSignalContext:
    open_positions: tuple[PaperPosition, ...]

    @property
    def open_buckets(self) -> tuple[str, ...]:
        return tuple(position.position_level or position.bucket for position in self.open_positions)

    @property
    def open_strategy_types(self) -> tuple[str, ...]:
        encoded: list[str] = []
        for position in self.open_positions:
            if position.strategy_kernel and position.position_level and position.trade_mode:
                encoded.append(
                    f"{position.strategy_kernel}|{position.position_level}|{position.side}|"
                    f"{position.trade_mode}|{position.lifecycle_state or ''}"
                )
            else:
                encoded.append(position.strategy_type)
        return tuple(encoded)


@dataclass(frozen=True)
class PaperStreamEvent:
    kline: Kline
    signal: SignalLike
    snapshot: PaperSnapshot
    closed_fill: PaperFill | None = None
    closed_fills: tuple[PaperFill, ...] = ()
    opened_position: PaperPosition | None = None
    rejected_signal: bool = False

    def __post_init__(self) -> None:
        if not self.closed_fills and self.closed_fill is not None:
            object.__setattr__(self, "closed_fills", (self.closed_fill,))
        elif self.closed_fills and self.closed_fill is None:
            object.__setattr__(self, "closed_fill", self.closed_fills[0])


async def run_paper_kline_stream(
    engine: PaperTradingEngine,
    source: AsyncIterable[Kline],
    signal_fn: SignalFn,
) -> PaperSnapshot:
    async for kline in source:
        closed_fills = engine.on_kline_all(kline)
        if closed_fills:
            continue
        snapshot = engine.snapshot()
        signal = _call_signal_fn(signal_fn, kline, snapshot)
        engine.on_signal(kline=kline, signal=signal)
    return engine.snapshot()


async def run_persistent_paper_kline_stream(
    config: PaperConfig,
    source: AsyncIterable[Kline],
    signal_fn: SignalFn,
    state_path: Path,
    event_sink: PaperStreamEventSink | None = None,
) -> PaperSnapshot:
    restored_snapshot = load_paper_snapshot(state_path)
    engine = (
        PaperTradingEngine.from_snapshot(config, restored_snapshot)
        if restored_snapshot is not None
        else PaperTradingEngine(config)
    )
    runtime_started_at_ms = (
        restored_snapshot.runtime_started_at_ms
        if restored_snapshot is not None and restored_snapshot.runtime_started_at_ms is not None
        else _now_ms()
    )
    signal_evaluations = list(restored_snapshot.signal_evaluations or []) if restored_snapshot is not None else []
    latest_snapshot = engine.snapshot()
    async for kline in source:
        closed_fills = engine.on_kline_all(kline)
        closed_fill = closed_fills[0] if closed_fills else None
        snapshot = engine.snapshot()
        opened_position = None
        rejected_signal = False
        if not closed_fills:
            signal = _call_signal_fn(signal_fn, kline, snapshot)
            rejected_count_before = snapshot.rejected_signals
            opened_position = engine.on_signal(kline=kline, signal=signal)
            rejected_signal = engine.snapshot().rejected_signals > rejected_count_before
        else:
            signal = StrategySignal(
                action="WAIT",
                strategy_type="SYSTEM",
                reason=["position closed on current kline"],
            )
        if not closed_fills:
            signal_evaluations = _append_signal_evaluation(
                signal_evaluations,
                _signal_evaluation_from(kline=kline, signal=signal, evaluated_at_ms=_now_ms()),
            )
        latest_snapshot = replace(
            engine.snapshot(),
            runtime_started_at_ms=runtime_started_at_ms,
            last_update_at_ms=_now_ms(),
            signal_evaluations=signal_evaluations,
        )
        save_paper_snapshot(latest_snapshot, state_path)
        if event_sink is not None:
            event_sink(
                PaperStreamEvent(
                    kline=kline,
                    signal=signal,
                    snapshot=latest_snapshot,
                    closed_fill=closed_fill,
                    closed_fills=tuple(closed_fills),
                    opened_position=opened_position,
                    rejected_signal=rejected_signal,
                )
            )
    return latest_snapshot


def _call_signal_fn(signal_fn: SignalFn, kline: Kline, snapshot: PaperSnapshot) -> SignalLike:
    has_position = snapshot.open_position is not None
    context = PaperSignalContext(open_positions=tuple(snapshot.open_positions))
    signature = inspect.signature(signal_fn)
    accepts_context = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    ) or len(signature.parameters) >= 3
    if accepts_context:
        return signal_fn(kline, has_position, context)
    return signal_fn(kline, has_position)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _signal_evaluation_from(
    kline: Kline,
    signal: SignalLike,
    evaluated_at_ms: int,
) -> PaperSignalEvaluation:
    return PaperSignalEvaluation(
        evaluated_at_ms=evaluated_at_ms,
        symbol=kline.symbol,
        interval=kline.interval,
        close=kline.close,
        action=signal.action,
        strategy_type=signal.strategy_type,
        reason=tuple(getattr(signal, "reason", []) or []),
        core_rules=tuple(getattr(signal, "core_rules", []) or []),
        chart_points=tuple(getattr(signal, "chart_points", []) or []),
        chart_timeframes={
            interval: tuple(points)
            for interval, points in (getattr(signal, "chart_timeframes", {}) or {}).items()
        },
        condition_statuses=tuple(getattr(signal, "condition_statuses", []) or []),
        nearest_strategy=getattr(signal, "nearest_strategy", {}) or {},
        strategy_kernel=getattr(signal, "strategy_kernel", None),
        position_level=getattr(signal, "position_level", None),
        trade_mode=getattr(signal, "trade_mode", None),
        market_regime=getattr(signal, "market_regime", None),
        lifecycle_state=getattr(signal, "lifecycle_state", None),
    )


def _append_signal_evaluation(
    evaluations: list[PaperSignalEvaluation],
    evaluation: PaperSignalEvaluation,
    max_items: int = 50,
) -> list[PaperSignalEvaluation]:
    without_current = [
        item
        for item in evaluations
        if not (item.symbol == evaluation.symbol and item.interval == evaluation.interval)
    ]
    return [*without_current, evaluation][-max_items:]
