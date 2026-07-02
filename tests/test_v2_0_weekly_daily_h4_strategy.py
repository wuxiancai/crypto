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
    atr: str = "2",
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
        atr=Decimal(atr),
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


def test_weekly_signal_uses_weekly_only_without_daily_confirmation():
    from app.strategy.weekly_daily_h4_strategy import WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
        )
    )

    assert decision.signal.action == "SHORT_ENTRY"
    assert decision.signal.position_level == "WEEKLY"
    assert decision.signal.trade_mode == "TREND"
    assert "weekly bear trend" in decision.signal.reason


def test_daily_short_under_weekly_bull_is_independent_daily_trend_not_rebound():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            daily=_frame(adx="19"),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            open_positions=(
                OpenPositionState("BTCUSDT", "LONG", PositionLevel.WEEKLY, TradeMode.TREND),
            ),
            focus_level=PositionLevel.DAILY,
        )
    )

    assert decision.signal.action == "SHORT_ENTRY"
    assert decision.signal.position_level == "DAILY"
    assert decision.signal.trade_mode == "TREND"
    assert decision.signal.strategy_type == "DAILY_SHORT_TREND"
    assert "daily independent short trend" in decision.signal.reason


def test_h4_long_under_daily_bear_is_independent_h4_breakout_not_rebound():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(adx="19"),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10", close="112", previous_high="108"),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND),
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.DAILY, TradeMode.TREND),
            ),
            focus_level=PositionLevel.H4,
        )
    )

    assert decision.signal.action == "LONG_ENTRY"
    assert decision.signal.position_level == "H4"
    assert decision.signal.trade_mode == "BREAKOUT"
    assert decision.signal.strategy_type == "H4_LONG_BREAKOUT"
    assert "h4 independent long breakout" in decision.signal.reason


def test_daily_existing_long_exits_on_full_bearish_reversal_before_new_entries():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            daily=_frame(fast="90", slow="100", slope="-1", di_plus="10", di_minus="30"),
            h4=_frame(),
            open_positions=(
                OpenPositionState("BTCUSDT", "LONG", PositionLevel.DAILY, TradeMode.TREND),
            ),
            focus_level=PositionLevel.DAILY,
        )
    )

    assert decision.signal.action == "EXIT_POSITION"
    assert decision.signal.position_level == "DAILY"
    assert "daily full bearish reversal" in decision.signal.reason


def test_h4_signal_is_not_blocked_by_strong_opposite_daily_trend():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(adx="30"),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10", close="112", previous_high="108"),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.DAILY, TradeMode.TREND),
            ),
            focus_level=PositionLevel.H4,
        )
    )

    assert decision.signal.action == "LONG_ENTRY"
    assert decision.signal.position_level == "H4"
    assert decision.signal.trade_mode == "BREAKOUT"
    assert decision.signal.strategy_type == "H4_LONG_BREAKOUT"


def test_entry_signal_uses_configured_risk_reward_and_atr_stop_cap():
    from app.strategy.position_hierarchy import PositionLevel
    from app.strategy.weekly_daily_h4_strategy import WeeklyDailyH4Config, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            daily=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            h4=_frame(
                close="100",
                fast="110",
                slow="100",
                slope="1",
                di_plus="30",
                di_minus="10",
                previous_low="80",
                atr="2",
            ),
            focus_level=PositionLevel.H4,
        ),
        WeeklyDailyH4Config(target_risk_reward=Decimal("3"), stop_atr_multiplier=Decimal("1.5")),
    )

    assert decision.signal.position_level == "H4"
    assert decision.signal.stop_loss == Decimal("97.0")
    assert decision.signal.take_profit == Decimal("109.0")


def test_weekly_same_direction_open_position_can_add():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND),
            ),
            focus_level=PositionLevel.WEEKLY,
        )
    )

    assert decision.signal.action == "SHORT_ENTRY"
    assert decision.signal.position_level == "WEEKLY"


def test_weekly_same_direction_open_position_is_blocked_when_additions_disabled():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import (
        OpenPositionState,
        WeeklyDailyH4Config,
        WeeklyDailyH4Input,
        build_weekly_daily_h4_decision,
    )

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(),
            h4=_frame(),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND),
            ),
        ),
        WeeklyDailyH4Config(allow_same_direction_add_positions=False),
    )

    assert decision.signal.action == "WAIT"
    assert "same direction additions disabled for WEEKLY" in decision.signal.reason


def test_daily_same_direction_open_position_is_limited_to_one_by_default():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND),
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.DAILY, TradeMode.TREND),
            ),
            focus_level=PositionLevel.DAILY,
        )
    )

    assert decision.signal.action == "WAIT"
    assert "same direction position limit reached for DAILY" in decision.signal.reason


def test_h4_same_direction_open_position_can_add():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(adx="19"),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10", close="112", previous_high="108"),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND),
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.DAILY, TradeMode.TREND),
                OpenPositionState("BTCUSDT", "LONG", PositionLevel.H4, TradeMode.REBOUND),
            ),
            focus_level=PositionLevel.H4,
        )
    )

    assert decision.signal.action == "LONG_ENTRY"
    assert decision.signal.position_level == "H4"
    assert decision.signal.trade_mode == "BREAKOUT"


def test_h4_same_direction_open_position_is_blocked_when_additions_disabled():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import (
        OpenPositionState,
        WeeklyDailyH4Config,
        WeeklyDailyH4Input,
        build_weekly_daily_h4_decision,
    )

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            open_positions=(
                OpenPositionState("BTCUSDT", "LONG", PositionLevel.H4, TradeMode.BREAKOUT),
            ),
            focus_level=PositionLevel.H4,
        ),
        WeeklyDailyH4Config(allow_same_direction_add_positions=False),
    )

    assert decision.signal.action == "WAIT"
    assert "same direction additions disabled for H4" in decision.signal.reason


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
    assert decision.signal.lifecycle_state == "REDUCED_TREND"


def test_weekly_reduction_stage_is_not_repeated_once_recorded():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(close="103", fast="90", slow="100", previous_high="110", di_plus="10", di_minus="30"),
            daily=_frame(),
            h4=_frame(),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND, "REDUCED_TREND"),
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.DAILY, TradeMode.TREND),
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.H4, TradeMode.CONTINUATION),
            ),
        )
    )

    assert decision.signal.action == "WAIT"
    assert "weekly reduction stages already handled" in decision.signal.reason


def test_weekly_reduction_allows_new_stage_after_prior_stage():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(close="96", fast="90", slow="100", previous_high="110", di_plus="35", di_minus="20"),
            daily=_frame(),
            h4=_frame(),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND, "REDUCED_TREND"),
            ),
        )
    )

    assert decision.signal.action == "REDUCE_POSITION"
    assert decision.signal.reason == ["weekly momentum broken"]
    assert decision.signal.lifecycle_state == "REDUCED_TREND|REDUCED_MOMENTUM"


def test_daily_existing_long_exits_daily_short_reversal_before_h4():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode
    from app.strategy.weekly_daily_h4_strategy import OpenPositionState, WeeklyDailyH4Input, build_weekly_daily_h4_decision

    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol="BTCUSDT",
            weekly=_frame(),
            daily=_frame(),
            h4=_frame(fast="110", slow="100", slope="1", di_plus="30", di_minus="10"),
            open_positions=(
                OpenPositionState("BTCUSDT", "SHORT", PositionLevel.WEEKLY, TradeMode.TREND),
                OpenPositionState(
                    symbol="BTCUSDT",
                    side="LONG",
                    position_level=PositionLevel.DAILY,
                    trade_mode=TradeMode.REBOUND,
                ),
                OpenPositionState("BTCUSDT", "LONG", PositionLevel.H4, TradeMode.REBOUND),
            ),
            focus_level=PositionLevel.DAILY,
        )
    )

    assert decision.signal.action == "EXIT_POSITION"
    assert decision.signal.position_level == "DAILY"
    assert "daily full bearish reversal" in decision.signal.reason


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
            focus_level=PositionLevel.H4,
        )
    )

    assert decision.signal.action == "WAIT"
