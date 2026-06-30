from decimal import Decimal


def test_generates_early_reversal_long_entry_and_caps_score():
    from app.strategy.reversal_strategy import ReversalSetup, build_reversal_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_reversal_signal(
        trend=TrendResult(
            trend_state="TRANSITION",
            main_strategy_action="WAIT",
            reversal_strategy_action="EVALUATE_REVERSAL_LONG",
            allow_long=False,
            allow_short=False,
            allow_reversal_long=True,
            allow_reversal_short=False,
            reason=[],
        ),
        setup=ReversalSetup(
            entry_price=Decimal("100"),
            ema50_15m=Decimal("99.5"),
            atr_15m=Decimal("1"),
            four_hour_no_new_low=True,
            four_hour_stop_structure=True,
            four_hour_near_or_above_ema50=True,
            one_hour_close_above_ema50=True,
            one_hour_near_or_above_ema200=True,
            one_hour_close_above_ema200=True,
            one_hour_higher_high=True,
            one_hour_higher_low=True,
            fifteen_close_above_ema200=True,
            fifteen_ema50_slope_up=True,
            fifteen_breakout_high_volume=True,
            fifteen_first_pullback_holds=True,
            fifteen_ema50_above_ema200=True,
            fifteen_reversal_candle=True,
            volume_confirmed=True,
            di_confirmed=True,
        ),
    )

    assert signal.action == "REVERSAL_LONG_ENTRY"
    assert signal.strategy_type == "REVERSAL_PROBE"
    assert signal.signal_level == "EARLY"
    assert signal.score == Decimal("100")
    assert signal.risk_pct == Decimal("0.002")
    assert signal.max_standard_position_pct == Decimal("0.2")
    assert signal.entry_price == Decimal("100")
    assert signal.stop_loss == Decimal("99")
    assert signal.take_profit == Decimal("102")
    assert signal.risk_reward == Decimal("2")


def test_generates_confirmed_reversal_short_entry():
    from app.strategy.reversal_strategy import ReversalSetup, build_reversal_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_reversal_signal(
        trend=TrendResult(
            trend_state="TRANSITION",
            main_strategy_action="WAIT",
            reversal_strategy_action="EVALUATE_REVERSAL_SHORT",
            allow_long=False,
            allow_short=False,
            allow_reversal_long=False,
            allow_reversal_short=True,
            reason=[],
        ),
        setup=ReversalSetup(
            entry_price=Decimal("100"),
            ema50_15m=Decimal("100.5"),
            atr_15m=Decimal("1"),
            four_hour_no_new_high=True,
            four_hour_exhaustion_structure=True,
            four_hour_near_or_below_ema50=True,
            one_hour_close_below_ema50=True,
            one_hour_near_or_below_ema200=True,
            one_hour_close_below_ema200=True,
            one_hour_ema50_slope_down=True,
            one_hour_lower_low=True,
            one_hour_lower_high=True,
            fifteen_close_below_ema200=True,
            fifteen_ema50_slope_down=True,
            fifteen_breakdown_low_volume=True,
            fifteen_first_rebound_rejects=True,
            fifteen_ema50_below_ema200=True,
            fifteen_rejection_candle=True,
            volume_confirmed=True,
        ),
    )

    assert signal.action == "REVERSAL_SHORT_ENTRY"
    assert signal.strategy_type == "REVERSAL_PROBE"
    assert signal.signal_level == "CONFIRMED"
    assert signal.score >= Decimal("70")
    assert signal.risk_pct == Decimal("0.003")
    assert signal.max_standard_position_pct == Decimal("0.5")
    assert signal.entry_price == Decimal("100")
    assert signal.stop_loss == Decimal("101")
    assert signal.take_profit == Decimal("98")
    assert signal.risk_reward == Decimal("2")


def test_blocks_reversal_long_when_chasing_too_far_from_ema50():
    from app.strategy.reversal_strategy import ReversalSetup, build_reversal_signal
    from app.strategy.trend_detector import TrendResult

    signal = build_reversal_signal(
        trend=TrendResult(
            trend_state="TRANSITION",
            main_strategy_action="WAIT",
            reversal_strategy_action="EVALUATE_REVERSAL_LONG",
            allow_long=False,
            allow_short=False,
            allow_reversal_long=True,
            allow_reversal_short=False,
            reason=[],
        ),
        setup=ReversalSetup(
            entry_price=Decimal("103"),
            ema50_15m=Decimal("100"),
            atr_15m=Decimal("2"),
            four_hour_no_new_low=True,
            one_hour_close_above_ema50=True,
            one_hour_near_or_above_ema200=True,
            fifteen_close_above_ema200=True,
            fifteen_ema50_slope_up=True,
            fifteen_breakout_high_volume=True,
            fifteen_first_pullback_holds=True,
        ),
    )

    assert signal.action == "WAIT"
    assert "reversal long chasing blocked" in signal.reason
