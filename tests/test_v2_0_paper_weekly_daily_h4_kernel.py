from decimal import Decimal

from app.data.quality import Kline


def _kline(
    close: str = "100",
    *,
    interval: str = "4h",
    high: str | None = None,
    low: str | None = None,
) -> Kline:
    return Kline(
        symbol="BTCUSDT",
        interval=interval,
        open_time=0,
        close_time=4 * 60 * 60 * 1000 - 1,
        open=Decimal(close),
        high=Decimal(high) if high is not None else Decimal(close) + Decimal("5"),
        low=Decimal(low) if low is not None else Decimal(close) - Decimal("5"),
        close=Decimal(close),
        volume=Decimal("1"),
    )


def test_paper_position_uses_new_level_for_conflict_not_legacy_bucket():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(initial_equity=Decimal("1000"), risk_per_trade_pct=Decimal("0.01"), slippage_pct=Decimal("0"))
    )
    first = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="DAILY_SHORT_TREND",
        bucket="DAILY",
        reason=["first daily"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        take_profit=Decimal("90"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="DAILY",
        trade_mode="TREND",
    )
    second = StrategySignal(
        action="LONG_ENTRY",
        strategy_type="DAILY_LONG_REBOUND",
        bucket="DAILY",
        reason=["daily rebound"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("90"),
        take_profit=Decimal("120"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="DAILY",
        trade_mode="REBOUND",
    )

    assert engine.on_signal(_kline(), first) is not None
    assert engine.on_signal(_kline(), second) is None
    assert engine.snapshot().rejected_signals == 1


def test_paper_allows_same_level_same_direction_add_position():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(initial_equity=Decimal("1000"), risk_per_trade_pct=Decimal("0.01"), slippage_pct=Decimal("0"))
    )
    first = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="DAILY_SHORT_TREND",
        bucket="DAILY",
        reason=["first daily short"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        take_profit=Decimal("90"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="DAILY",
        trade_mode="TREND",
    )
    add = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="DAILY_SHORT_TREND",
        bucket="DAILY",
        reason=["add daily short"],
        entry_price=Decimal("99"),
        stop_loss=Decimal("104"),
        take_profit=Decimal("89"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="DAILY",
        trade_mode="TREND",
    )

    assert engine.on_signal(_kline(), first) is not None
    assert engine.on_signal(_kline("99"), add) is not None

    snapshot = engine.snapshot()
    assert len(snapshot.open_positions) == 2
    assert {position.position_level for position in snapshot.open_positions} == {"DAILY"}
    assert {position.side for position in snapshot.open_positions} == {"SHORT"}
    assert snapshot.rejected_signals == 0


def test_paper_allows_different_levels_with_opposite_directions():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(initial_equity=Decimal("1000"), risk_per_trade_pct=Decimal("0.01"), slippage_pct=Decimal("0"))
    )
    weekly_long = StrategySignal(
        action="LONG_ENTRY",
        strategy_type="WEEKLY_LONG_TREND",
        bucket="WEEKLY",
        reason=["weekly long"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("90"),
        take_profit=Decimal("120"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="WEEKLY",
        trade_mode="TREND",
    )
    daily_short = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="DAILY_SHORT_REBOUND",
        bucket="DAILY",
        reason=["daily short"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        take_profit=Decimal("90"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="DAILY",
        trade_mode="REBOUND",
    )

    assert engine.on_signal(_kline(), weekly_long) is not None
    assert engine.on_signal(_kline(), daily_short) is not None

    snapshot = engine.snapshot()
    assert len(snapshot.open_positions) == 2
    assert {(position.position_level, position.side) for position in snapshot.open_positions} == {
        ("WEEKLY", "LONG"),
        ("DAILY", "SHORT"),
    }


def test_paper_weekly_reduce_position_partially():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(initial_equity=Decimal("1000"), risk_per_trade_pct=Decimal("0.01"), slippage_pct=Decimal("0"))
    )
    entry = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="WEEKLY_SHORT_TREND",
        bucket="WEEKLY",
        reason=["weekly"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        take_profit=Decimal("90"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="WEEKLY",
        trade_mode="TREND",
    )
    engine.on_signal(_kline(), entry)
    before_qty = engine.snapshot().open_positions[0].quantity

    reduce = StrategySignal(
        action="REDUCE_POSITION",
        strategy_type="WEEKLY_SHORT_TREND",
        bucket="WEEKLY",
        reason=["weekly trend damage"],
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="WEEKLY",
        trade_mode="TREND",
        reduce_pct=Decimal("0.5"),
    )
    fill = engine.on_signal(_kline("98"), reduce)

    assert fill is not None
    assert engine.snapshot().open_positions[0].quantity == before_qty * Decimal("0.5")
    assert engine.snapshot().fills[-1].exit_reason == "KERNEL_STAGED_REDUCTION"


def test_paper_weekly_reduce_position_records_next_lifecycle_stage():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(initial_equity=Decimal("1000"), risk_per_trade_pct=Decimal("0.01"), slippage_pct=Decimal("0"))
    )
    entry = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="WEEKLY_SHORT_TREND",
        bucket="WEEKLY",
        reason=["weekly"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        take_profit=Decimal("90"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="WEEKLY",
        trade_mode="TREND",
    )
    engine.on_signal(_kline(), entry)
    reduce = StrategySignal(
        action="REDUCE_POSITION",
        strategy_type="WEEKLY_SHORT_TREND",
        bucket="WEEKLY",
        reason=["weekly trend damage"],
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="WEEKLY",
        trade_mode="TREND",
        reduce_pct=Decimal("0.5"),
        lifecycle_state="REDUCED_TREND",
    )

    engine.on_signal(_kline("98"), reduce)

    assert engine.snapshot().open_positions[0].lifecycle_state == "REDUCED_TREND"


def test_weekly_position_ignores_regular_stop_and_take_profit_until_kernel_management_signal():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("1000"),
            risk_per_trade_pct=Decimal("0.01"),
            slippage_pct=Decimal("0"),
            leverage=Decimal("2"),
        )
    )
    entry = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="WEEKLY_SHORT_TREND",
        bucket="WEEKLY",
        reason=["weekly"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        take_profit=Decimal("90"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="WEEKLY",
        trade_mode="TREND",
    )

    assert engine.on_signal(_kline(), entry) is not None

    stop_fill = engine.on_kline(_kline("100", high="106", low="99"))
    take_profit_fill = engine.on_kline(_kline("92", high="94", low="88"))

    snapshot = engine.snapshot()
    assert stop_fill is None
    assert take_profit_fill is None
    assert snapshot.open_positions
    assert snapshot.open_positions[0].position_level == "WEEKLY"
    assert snapshot.open_positions[0].trailing_active is False
    assert snapshot.fills == []


def test_weekly_position_uses_independent_leverage_for_liquidation_guard():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("1000"),
            risk_per_trade_pct=Decimal("0.01"),
            slippage_pct=Decimal("0"),
            leverage=Decimal("10"),
            weekly_leverage=Decimal("2"),
        )
    )
    entry = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="WEEKLY_SHORT_TREND",
        bucket="WEEKLY",
        reason=["weekly"],
        entry_price=Decimal("100"),
        stop_loss=Decimal("112"),
        take_profit=Decimal("76"),
        strategy_kernel="WEEKLY_DAILY_H4_V1",
        position_level="WEEKLY",
        trade_mode="TREND",
    )

    position = engine.on_signal(_kline(), entry)

    assert position is not None
    assert position.leverage == Decimal("2")
