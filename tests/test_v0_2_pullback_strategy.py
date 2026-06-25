from decimal import Decimal


def test_generates_main_long_entry_on_uptrend_pullback_confirmation():
    from app.strategy.pullback_strategy import EntryFrame, build_pullback_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_pullback_signal(
        trend=TrendResult(
            trend_state="UPTREND",
            main_strategy_action="EVALUATE_LONG",
            reversal_strategy_action="DISABLED",
            allow_long=True,
            allow_short=False,
            allow_reversal_long=False,
            allow_reversal_short=False,
            reason=[],
        ),
        frame=EntryFrame(
            close=Decimal("105"),
            previous_close=Decimal("101"),
            ema50=Decimal("104"),
            atr=Decimal("2"),
            recent_swing_low=Decimal("99"),
            recent_swing_high=Decimal("115"),
        ),
    )

    assert signal.action == "LONG_ENTRY"
    assert signal.strategy_type == "TREND_PULLBACK"
    assert signal.entry_price == Decimal("105")
    assert signal.stop_loss == Decimal("99")
    assert signal.take_profit == Decimal("117")
    assert signal.risk_reward == Decimal("2")
    assert signal.reason == [
        "main trend uptrend",
        "price pulled back to ema50 zone",
        "bullish 15m confirmation",
        "risk reward accepted",
    ]


def test_generates_main_short_entry_on_downtrend_rebound_confirmation():
    from app.strategy.pullback_strategy import EntryFrame, build_pullback_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_pullback_signal(
        trend=TrendResult(
            trend_state="DOWNTREND",
            main_strategy_action="EVALUATE_SHORT",
            reversal_strategy_action="DISABLED",
            allow_long=False,
            allow_short=True,
            allow_reversal_long=False,
            allow_reversal_short=False,
            reason=[],
        ),
        frame=EntryFrame(
            close=Decimal("95"),
            previous_close=Decimal("99"),
            ema50=Decimal("96"),
            atr=Decimal("2"),
            recent_swing_low=Decimal("85"),
            recent_swing_high=Decimal("101"),
        ),
    )

    assert signal.action == "SHORT_ENTRY"
    assert signal.strategy_type == "TREND_PULLBACK"
    assert signal.entry_price == Decimal("95")
    assert signal.stop_loss == Decimal("101")
    assert signal.take_profit == Decimal("83")
    assert signal.risk_reward == Decimal("2")
    assert signal.reason == [
        "main trend downtrend",
        "price rebounded to ema50 zone",
        "bearish 15m confirmation",
        "risk reward accepted",
    ]


def test_generates_main_short_entry_when_candle_wicks_into_ema50_zone_then_rejects():
    from app.strategy.pullback_strategy import EntryFrame, build_pullback_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_pullback_signal(
        trend=TrendResult(
            trend_state="DOWNTREND",
            main_strategy_action="EVALUATE_SHORT",
            reversal_strategy_action="DISABLED",
            allow_long=False,
            allow_short=True,
            allow_reversal_long=False,
            allow_reversal_short=False,
            reason=[],
        ),
        frame=EntryFrame(
            close=Decimal("95"),
            previous_close=Decimal("94"),
            ema50=Decimal("100"),
            atr=Decimal("2"),
            recent_swing_low=Decimal("90"),
            recent_swing_high=Decimal("105"),
            open=Decimal("98"),
            high=Decimal("99"),
            low=Decimal("94"),
        ),
    )

    assert signal.action == "SHORT_ENTRY"
    assert signal.entry_price == Decimal("95")
    assert signal.reason == [
        "main trend downtrend",
        "price rebounded to ema50 zone",
        "bearish 15m confirmation",
        "risk reward accepted",
    ]


def test_strict_short_rebound_requires_close_below_fast_average():
    from app.strategy.pullback_strategy import EntryFrame, PullbackTriggerConfig, build_pullback_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_pullback_signal(
        trend=TrendResult(
            trend_state="DOWNTREND",
            main_strategy_action="EVALUATE_SHORT",
            reversal_strategy_action="DISABLED",
            allow_long=False,
            allow_short=True,
            allow_reversal_long=False,
            allow_reversal_short=False,
            reason=[],
        ),
        frame=EntryFrame(
            close=Decimal("100.5"),
            previous_close=Decimal("101"),
            ema50=Decimal("100"),
            atr=Decimal("2"),
            recent_swing_low=Decimal("90"),
            recent_swing_high=Decimal("105"),
            open=Decimal("101"),
            high=Decimal("101.5"),
            low=Decimal("99.5"),
        ),
        trigger_config=PullbackTriggerConfig(
            zone_atr_multiplier=Decimal("0.5"),
            require_close_beyond_ema=True,
        ),
    )

    assert signal.action == "WAIT"
    assert "price not in ema50 rebound zone" in signal.reason


def test_strict_short_rebound_accepts_rejection_candle_back_below_fast_average():
    from app.strategy.pullback_strategy import EntryFrame, PullbackTriggerConfig, build_pullback_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_pullback_signal(
        trend=TrendResult(
            trend_state="DOWNTREND",
            main_strategy_action="EVALUATE_SHORT",
            reversal_strategy_action="DISABLED",
            allow_long=False,
            allow_short=True,
            allow_reversal_long=False,
            allow_reversal_short=False,
            reason=[],
        ),
        frame=EntryFrame(
            close=Decimal("99.4"),
            previous_close=Decimal("101"),
            ema50=Decimal("100"),
            atr=Decimal("2"),
            recent_swing_low=Decimal("90"),
            recent_swing_high=Decimal("105"),
            open=Decimal("101"),
            high=Decimal("101.5"),
            low=Decimal("99"),
        ),
        trigger_config=PullbackTriggerConfig(
            zone_atr_multiplier=Decimal("0.5"),
            require_close_beyond_ema=True,
        ),
    )

    assert signal.action == "SHORT_ENTRY"
    assert signal.reason == [
        "main trend downtrend",
        "price rebounded to ema50 zone",
        "bearish 15m confirmation",
        "risk reward accepted",
    ]


def test_blocks_pullback_signal_when_risk_reward_is_too_low():
    from app.strategy.pullback_strategy import EntryFrame, build_pullback_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_pullback_signal(
        trend=TrendResult(
            trend_state="UPTREND",
            main_strategy_action="EVALUATE_LONG",
            reversal_strategy_action="DISABLED",
            allow_long=True,
            allow_short=False,
            allow_reversal_long=False,
            allow_reversal_short=False,
            reason=[],
        ),
        frame=EntryFrame(
            close=Decimal("105"),
            previous_close=Decimal("101"),
            ema50=Decimal("104"),
            atr=Decimal("2"),
            recent_swing_low=Decimal("100"),
            recent_swing_high=Decimal("108"),
        ),
        min_risk_reward=Decimal("3"),
    )

    assert signal.action == "WAIT"
    assert "configured risk reward too low" in signal.reason
