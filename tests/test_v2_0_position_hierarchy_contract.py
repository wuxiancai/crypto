from decimal import Decimal


def test_position_levels_are_only_weekly_daily_h4():
    from app.strategy.position_hierarchy import PositionLevel

    assert [item.value for item in PositionLevel] == ["WEEKLY", "DAILY", "H4"]


def test_trade_modes_are_attributes_not_position_levels():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode

    assert "BREAKOUT" not in [item.value for item in PositionLevel]
    assert TradeMode.BREAKOUT.value == "BREAKOUT"


def test_legacy_buckets_are_not_canonical_levels():
    from app.strategy.position_hierarchy import legacy_bucket_to_position_level

    assert legacy_bucket_to_position_level("DAY_CORE") is None
    assert legacy_bucket_to_position_level("FOUR_HOUR_ADDON") is None
    assert legacy_bucket_to_position_level("FOUR_HOUR_HEDGE") is None


def test_signal_carries_new_kernel_identity():
    from app.strategy.position_hierarchy import PositionLevel, StrategyKernel, TradeMode
    from app.strategy.signal_router import StrategySignal

    signal = StrategySignal(
        action="SHORT_ENTRY",
        strategy_type="WEEKLY_SHORT_TREND",
        reason=["weekly bear"],
        strategy_kernel=StrategyKernel.WEEKLY_DAILY_H4_V1.value,
        position_level=PositionLevel.WEEKLY.value,
        trade_mode=TradeMode.TREND.value,
        reduce_pct=Decimal("0.5"),
    )

    assert signal.strategy_kernel == "WEEKLY_DAILY_H4_V1"
    assert signal.position_level == "WEEKLY"
    assert signal.trade_mode == "TREND"
    assert signal.reduce_pct == Decimal("0.5")
