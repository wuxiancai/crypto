from decimal import Decimal

from app.data.quality import INTERVAL_MS, Kline


def _series(symbol: str, interval: str, start: Decimal, step: Decimal, count: int = 90) -> tuple[Kline, ...]:
    rows = []
    interval_ms = INTERVAL_MS[interval]
    for index in range(count):
        close = start + step * Decimal(index)
        open_time = index * interval_ms
        rows.append(
            Kline(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + interval_ms - 1,
                open=close + Decimal("1"),
                high=close + Decimal("2"),
                low=close - Decimal("2"),
                close=close,
                volume=Decimal("100"),
            )
        )
    return tuple(rows)


def test_realtime_adapter_uses_weekly_daily_h4_kernel_without_old_layered_switch():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "1w": _series("BTCUSDT", "1w", Decimal("200"), Decimal("-1")),
            "1d": _series("BTCUSDT", "1d", Decimal("190"), Decimal("-1")),
            "4h": _series("BTCUSDT", "4h", Decimal("180"), Decimal("-1")),
        },
    )

    signal = build_realtime_strategy_signal(frame, RealtimeStrategyConfig())

    assert signal.strategy_kernel == "WEEKLY_DAILY_H4_V1"
    assert signal.position_level == "WEEKLY"
    assert signal.strategy_type.startswith("WEEKLY_")
    assert signal.bucket == "WEEKLY"


def test_default_realtime_signal_fn_blocks_weekly_management_on_h4_events(monkeypatch):
    from app.paper import live_runner
    from app.paper.stream import PaperSignalContext
    from app.paper.trading import PaperPosition
    from app.strategy.signal_router import StrategySignal

    def weekly_reduce(*args, **kwargs):
        return StrategySignal(
            action="REDUCE_POSITION",
            strategy_type="WEEKLY_SHORT_TREND",
            bucket="WEEKLY",
            reason=["weekly trend defense broken"],
            strategy_kernel="WEEKLY_DAILY_H4_V1",
            position_level="WEEKLY",
            trade_mode="TREND",
            reduce_pct=Decimal("0.5"),
        )

    monkeypatch.setattr(live_runner, "build_realtime_strategy_signal", weekly_reduce)
    signal_fn = live_runner.build_default_realtime_signal_fn(
        live_runner.default_paper_strategy_config(),
        warmup_klines=[
            *_series("BTCUSDT", "1w", Decimal("200"), Decimal("-1")),
            *_series("BTCUSDT", "1d", Decimal("190"), Decimal("-1")),
            *_series("BTCUSDT", "4h", Decimal("180"), Decimal("-1")),
        ],
    )
    context = PaperSignalContext(
        open_positions=(
            PaperPosition(
                symbol="BTCUSDT",
                side="SHORT",
                strategy_type="WEEKLY_SHORT_TREND",
                entry_time=0,
                entry_price=Decimal("100"),
                stop_loss=Decimal("120"),
                take_profit=Decimal("60"),
                quantity=Decimal("1"),
                entry_fee=Decimal("0"),
                bucket="WEEKLY",
                strategy_kernel="WEEKLY_DAILY_H4_V1",
                position_level="WEEKLY",
                trade_mode="TREND",
            ),
        )
    )

    signal = signal_fn(_series("BTCUSDT", "4h", Decimal("90"), Decimal("-1"), count=1)[0], True, context)

    assert signal.action == "WAIT"
    assert signal.reason == ["weekly management waits for weekly close"]


def test_default_realtime_signal_fn_allows_weekly_management_on_weekly_events(monkeypatch):
    from app.paper import live_runner
    from app.paper.stream import PaperSignalContext
    from app.paper.trading import PaperPosition
    from app.strategy.signal_router import StrategySignal

    def weekly_reduce(*args, **kwargs):
        return StrategySignal(
            action="REDUCE_POSITION",
            strategy_type="WEEKLY_SHORT_TREND",
            bucket="WEEKLY",
            reason=["weekly trend defense broken"],
            strategy_kernel="WEEKLY_DAILY_H4_V1",
            position_level="WEEKLY",
            trade_mode="TREND",
            reduce_pct=Decimal("0.5"),
        )

    monkeypatch.setattr(live_runner, "build_realtime_strategy_signal", weekly_reduce)
    signal_fn = live_runner.build_default_realtime_signal_fn(
        live_runner.default_paper_strategy_config(),
        warmup_klines=[
            *_series("BTCUSDT", "1w", Decimal("200"), Decimal("-1")),
            *_series("BTCUSDT", "1d", Decimal("190"), Decimal("-1")),
            *_series("BTCUSDT", "4h", Decimal("180"), Decimal("-1")),
        ],
    )
    context = PaperSignalContext(
        open_positions=(
            PaperPosition(
                symbol="BTCUSDT",
                side="SHORT",
                strategy_type="WEEKLY_SHORT_TREND",
                entry_time=0,
                entry_price=Decimal("100"),
                stop_loss=Decimal("120"),
                take_profit=Decimal("60"),
                quantity=Decimal("1"),
                entry_fee=Decimal("0"),
                bucket="WEEKLY",
                strategy_kernel="WEEKLY_DAILY_H4_V1",
                position_level="WEEKLY",
                trade_mode="TREND",
            ),
        )
    )

    signal = signal_fn(_series("BTCUSDT", "1w", Decimal("90"), Decimal("-1"), count=1)[0], True, context)

    assert signal.action == "REDUCE_POSITION"
    assert signal.position_level == "WEEKLY"


def test_default_realtime_signal_fn_allows_daily_signal_only_on_daily_events(monkeypatch):
    from app.paper import live_runner
    from app.strategy.signal_router import StrategySignal

    def daily_short(*args, **kwargs):
        return StrategySignal(
            action="SHORT_ENTRY",
            strategy_type="DAILY_SHORT_TREND",
            bucket="DAILY",
            reason=["daily short"],
            strategy_kernel="WEEKLY_DAILY_H4_V1",
            position_level="DAILY",
            trade_mode="TREND",
        )

    monkeypatch.setattr(live_runner, "build_realtime_strategy_signal", daily_short)
    signal_fn = live_runner.build_default_realtime_signal_fn(
        live_runner.default_paper_strategy_config(),
        warmup_klines=[
            *_series("BTCUSDT", "1w", Decimal("200"), Decimal("-1")),
            *_series("BTCUSDT", "1d", Decimal("190"), Decimal("-1")),
            *_series("BTCUSDT", "4h", Decimal("180"), Decimal("-1")),
        ],
    )

    h4_signal = signal_fn(_series("BTCUSDT", "4h", Decimal("90"), Decimal("-1"), count=1)[0], True)
    daily_signal = signal_fn(_series("BTCUSDT", "1d", Decimal("90"), Decimal("-1"), count=1)[0], True)

    assert h4_signal.action == "WAIT"
    assert h4_signal.reason == ["daily signal waits for daily close"]
    assert daily_signal.action == "SHORT_ENTRY"
    assert daily_signal.position_level == "DAILY"


def test_default_realtime_signal_fn_allows_h4_signal_only_on_h4_events(monkeypatch):
    from app.paper import live_runner
    from app.strategy.signal_router import StrategySignal

    def h4_long(*args, **kwargs):
        return StrategySignal(
            action="LONG_ENTRY",
            strategy_type="H4_LONG_REBOUND",
            bucket="H4",
            reason=["h4 long"],
            strategy_kernel="WEEKLY_DAILY_H4_V1",
            position_level="H4",
            trade_mode="REBOUND",
        )

    monkeypatch.setattr(live_runner, "build_realtime_strategy_signal", h4_long)
    signal_fn = live_runner.build_default_realtime_signal_fn(
        live_runner.default_paper_strategy_config(),
        warmup_klines=[
            *_series("BTCUSDT", "1w", Decimal("200"), Decimal("-1")),
            *_series("BTCUSDT", "1d", Decimal("190"), Decimal("-1")),
            *_series("BTCUSDT", "4h", Decimal("180"), Decimal("-1")),
        ],
    )

    daily_signal = signal_fn(_series("BTCUSDT", "1d", Decimal("90"), Decimal("-1"), count=1)[0], True)
    h4_signal = signal_fn(_series("BTCUSDT", "4h", Decimal("90"), Decimal("-1"), count=1)[0], True)

    assert daily_signal.action == "WAIT"
    assert daily_signal.reason == ["h4 signal waits for h4 close"]
    assert h4_signal.action == "LONG_ENTRY"
    assert h4_signal.position_level == "H4"


def test_adapter_preserves_multi_stage_weekly_lifecycle_state():
    from app.paper.strategy_adapter import _open_position_states

    states = _open_position_states(
        open_buckets=(),
        open_strategy_types=(
            "WEEKLY_DAILY_H4_V1|WEEKLY|SHORT|TREND|REDUCED_TREND|REDUCED_MOMENTUM",
        ),
    )

    assert states[0].lifecycle_state == "REDUCED_TREND|REDUCED_MOMENTUM"
