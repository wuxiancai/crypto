from decimal import Decimal


def _frame(
    *,
    close: str = "100",
    fast: str = "90",
    slow: str = "100",
    slope: str = "-1",
    adx: str = "25",
    di_plus: str = "10",
    di_minus: str = "30",
    previous_high: str = "105",
    previous_low: str = "95",
    boll_upper: str = "110",
    boll_lower: str = "90",
    boll_middle: str = "100",
):
    from app.strategy.weekly_daily_h4_strategy import TrendFrame

    return TrendFrame(
        close=Decimal(close),
        fast_ma=Decimal(fast),
        slow_ma=Decimal(slow),
        fast_ma_slope=Decimal(slope),
        adx=Decimal(adx),
        di_plus=Decimal(di_plus),
        di_minus=Decimal(di_minus),
        previous_high=Decimal(previous_high),
        previous_low=Decimal(previous_low),
        boll_upper=Decimal(boll_upper),
        boll_lower=Decimal(boll_lower),
        boll_middle=Decimal(boll_middle),
        atr=Decimal("2"),
    )


def test_weekly_bear_and_daily_death_cross_opens_weekly_short():
    from app.strategy.weekly_daily_h4_strategy import WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(symbol="BTCUSDT", weekly=_frame(), daily=_frame(), h4=_frame())
    )

    assert decision.signal.action == "SHORT_ENTRY"
    assert decision.signal.strategy_kernel == "WEEKLY_DAILY_H4_V1"
    assert decision.signal.position_level == "WEEKLY"
    assert decision.signal.trade_mode == "TREND"
    assert decision.signal.bucket == "WEEKLY"


def test_weekly_short_uses_weekly_ma60_for_lifecycle_defense_not_h4_or_structure_high():
    from app.strategy.weekly_daily_h4_strategy import WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(close="100", slow="112", previous_high="130", previous_low="80"),
            daily=_frame(close="96", previous_high="110", previous_low="90"),
            h4=_frame(close="88", previous_high="92", previous_low="84"),
        )
    )

    assert decision.signal.action == "SHORT_ENTRY"
    assert decision.signal.position_level == "WEEKLY"
    assert decision.signal.entry_price == Decimal("100")
    assert decision.signal.stop_loss == Decimal("112")
    assert decision.signal.take_profit == Decimal("76")


def test_weekly_trend_damage_reduces_weekly_position_before_forced_exit():
    from app.strategy.position_hierarchy import LifecycleState, PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(close="103", fast="90", slow="100", di_plus="10", di_minus="30"),
            daily=_frame(),
            h4=_frame(),
            open_positions=(
                OpenPositionState(
                    symbol="BTCUSDT",
                    side="SHORT",
                    position_level=PositionLevel.WEEKLY,
                    trade_mode=TradeMode.TREND,
                    lifecycle_state=LifecycleState.OPEN,
                ),
            ),
        )
    )

    assert decision.signal.action == "REDUCE_POSITION"
    assert decision.signal.position_level == "WEEKLY"
    assert decision.signal.reduce_pct == Decimal("0.5")


def test_daily_position_is_mutually_exclusive():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            open_positions=(
                OpenPositionState(
                    symbol="BTCUSDT",
                    side="LONG",
                    position_level=PositionLevel.DAILY,
                    trade_mode=TradeMode.REBOUND,
                ),
            ),
        )
    )

    assert decision.signal.action == "WAIT"


def test_h4_breakout_requires_bollinger_expansion():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    narrow_h4 = _frame(
        close="94",
        previous_low="95",
        boll_upper="100.2",
        boll_lower="99.8",
        boll_middle="100",
    )
    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            h4=narrow_h4,
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND),
                OpenPositionState("BTCUSDT", "LONG", PositionLevel.DAILY, TradeMode.REBOUND),
            ),
        )
    )

    assert decision.signal.action == "WAIT"
