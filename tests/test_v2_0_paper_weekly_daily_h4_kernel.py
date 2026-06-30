from decimal import Decimal

from app.data.quality import Kline


def _kline(close: str = "100") -> Kline:
    return Kline(
        symbol="BTCUSDT",
        interval="4h",
        open_time=0,
        close_time=4 * 60 * 60 * 1000 - 1,
        open=Decimal(close),
        high=Decimal(close) + Decimal("5"),
        low=Decimal(close) - Decimal("5"),
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
