from decimal import Decimal


def test_detects_uptrend_for_main_long_strategy():
    from app.strategy.trend_detector import TrendFrame, detect_trend

    result = detect_trend(
        four_hour=TrendFrame(
            close=Decimal("120"),
            ema50=Decimal("110"),
            ema200=Decimal("100"),
            ema50_slope=Decimal("1"),
            di_plus=Decimal("30"),
            di_minus=Decimal("10"),
            adx=Decimal("25"),
        ),
        one_hour=TrendFrame(
            close=Decimal("118"),
            ema50=Decimal("112"),
            ema200=Decimal("105"),
            ema50_slope=Decimal("1"),
            di_plus=Decimal("28"),
            di_minus=Decimal("12"),
            adx=Decimal("23"),
        ),
    )

    assert result.trend_state == "UPTREND"
    assert result.main_strategy_action == "EVALUATE_LONG"
    assert result.reversal_strategy_action == "DISABLED"
    assert result.allow_long is True


def test_transition_allows_reversal_long_when_4h_down_1h_up():
    from app.strategy.trend_detector import TrendFrame, detect_trend

    result = detect_trend(
        four_hour=TrendFrame(
            close=Decimal("90"),
            ema50=Decimal("95"),
            ema200=Decimal("100"),
            ema50_slope=Decimal("-1"),
            di_plus=Decimal("10"),
            di_minus=Decimal("30"),
            adx=Decimal("25"),
        ),
        one_hour=TrendFrame(
            close=Decimal("108"),
            ema50=Decimal("103"),
            ema200=Decimal("100"),
            ema50_slope=Decimal("1"),
            di_plus=Decimal("28"),
            di_minus=Decimal("12"),
            adx=Decimal("23"),
        ),
    )

    assert result.trend_state == "TRANSITION"
    assert result.main_strategy_action == "WAIT"
    assert result.reversal_strategy_action == "EVALUATE_REVERSAL_LONG"
    assert result.allow_reversal_long is True
    assert result.allow_long is False

