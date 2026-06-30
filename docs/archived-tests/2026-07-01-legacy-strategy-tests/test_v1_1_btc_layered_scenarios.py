from decimal import Decimal


def test_btc_2025_may_style_daily_short_core_signal():
    from app.strategy.layered_strategy import (
        LayeredEntryFrame,
        LayeredStrategyConfig,
        LayeredStrategyInput,
        TrendSnapshot,
        build_layered_strategy_decision,
    )

    decision = build_layered_strategy_decision(
        LayeredStrategyInput(
            symbol="BTCUSDT",
            daily=TrendSnapshot(
                close=Decimal("79000"),
                fast_ma=Decimal("80500"),
                slow_ma=Decimal("81200"),
                fast_ma_slope=Decimal("-180"),
                adx=Decimal("26"),
                di_plus=Decimal("14"),
                di_minus=Decimal("31"),
            ),
            four_hour=TrendSnapshot(
                close=Decimal("78794"),
                fast_ma=Decimal("80612"),
                slow_ma=Decimal("82460"),
                fast_ma_slope=Decimal("-260"),
                adx=Decimal("25"),
                di_plus=Decimal("13"),
                di_minus=Decimal("34"),
            ),
            one_hour=TrendSnapshot(
                close=Decimal("78650"),
                fast_ma=Decimal("79400"),
                slow_ma=Decimal("80200"),
                fast_ma_slope=Decimal("-120"),
                adx=Decimal("24"),
                di_plus=Decimal("15"),
                di_minus=Decimal("30"),
            ),
            entry=LayeredEntryFrame(
                close=Decimal("78794"),
                open=Decimal("80460"),
                high=Decimal("80558"),
                low=Decimal("78753"),
                fast_ma=Decimal("79800"),
                atr=Decimal("900"),
                recent_swing_low=Decimal("78000"),
                recent_swing_high=Decimal("80600"),
            ),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is not None
    assert decision.signal.strategy_type == "SHORT_DAY_CORE"
    assert decision.signal.bucket == "DAY_CORE"
    assert "SHORT_DAY_CORE" in decision.candidates


def test_btc_2026_june_daily_short_with_4h_rebound_hedge_signal():
    from app.strategy.layered_strategy import (
        LayeredEntryFrame,
        LayeredStrategyConfig,
        LayeredStrategyInput,
        TrendSnapshot,
        build_layered_strategy_decision,
    )

    decision = build_layered_strategy_decision(
        LayeredStrategyInput(
            symbol="BTCUSDT",
            daily=TrendSnapshot(
                close=Decimal("62430"),
                fast_ma=Decimal("65000"),
                slow_ma=Decimal("70500"),
                fast_ma_slope=Decimal("-320"),
                adx=Decimal("27"),
                di_plus=Decimal("16"),
                di_minus=Decimal("33"),
            ),
            four_hour=TrendSnapshot(
                close=Decimal("64275"),
                fast_ma=Decimal("63600"),
                slow_ma=Decimal("62800"),
                fast_ma_slope=Decimal("210"),
                adx=Decimal("23"),
                di_plus=Decimal("29"),
                di_minus=Decimal("17"),
            ),
            one_hour=TrendSnapshot(
                close=Decimal("64600"),
                fast_ma=Decimal("64200"),
                slow_ma=Decimal("63500"),
                fast_ma_slope=Decimal("110"),
                adx=Decimal("22"),
                di_plus=Decimal("28"),
                di_minus=Decimal("18"),
            ),
            entry=LayeredEntryFrame(
                close=Decimal("64650"),
                open=Decimal("64200"),
                high=Decimal("64800"),
                low=Decimal("63900"),
                fast_ma=Decimal("64100"),
                atr=Decimal("450"),
                recent_swing_low=Decimal("63600"),
                recent_swing_high=Decimal("65000"),
            ),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is not None
    assert decision.signal.strategy_type == "LONG_4H_HEDGE"
    assert decision.signal.bucket == "FOUR_HOUR_HEDGE"
    assert "SHORT_DAY_CORE" in decision.candidates
    assert "LONG_4H_HEDGE" in decision.candidates

