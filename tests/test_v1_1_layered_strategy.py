from decimal import Decimal


def test_layered_strategy_generates_short_day_core_from_daily_downtrend():
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
                close=Decimal("62000"),
                fast_ma=Decimal("64000"),
                slow_ma=Decimal("66000"),
                fast_ma_slope=Decimal("-200"),
                adx=Decimal("25"),
                di_plus=Decimal("15"),
                di_minus=Decimal("30"),
            ),
            four_hour=TrendSnapshot(
                close=Decimal("61800"),
                fast_ma=Decimal("62500"),
                slow_ma=Decimal("64000"),
                fast_ma_slope=Decimal("-150"),
                adx=Decimal("24"),
                di_plus=Decimal("14"),
                di_minus=Decimal("31"),
            ),
            one_hour=TrendSnapshot(
                close=Decimal("61750"),
                fast_ma=Decimal("62200"),
                slow_ma=Decimal("63500"),
                fast_ma_slope=Decimal("-80"),
                adx=Decimal("23"),
                di_plus=Decimal("16"),
                di_minus=Decimal("29"),
            ),
            entry=LayeredEntryFrame(
                close=Decimal("61600"),
                open=Decimal("62100"),
                high=Decimal("62300"),
                low=Decimal("61500"),
                fast_ma=Decimal("62000"),
                atr=Decimal("300"),
                recent_swing_low=Decimal("61000"),
                recent_swing_high=Decimal("62800"),
            ),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is not None
    assert decision.signal.strategy_type == "SHORT_DAY_CORE"
    assert decision.signal.action == "SHORT_ENTRY"
    assert decision.signal.bucket == "DAY_CORE"
    assert decision.signal.entry_price == Decimal("61600")
    assert decision.signal.stop_loss == Decimal("62800")
    assert decision.signal.take_profit == Decimal("59200")
    assert "SHORT_DAY_CORE" in decision.candidates


def test_layered_strategy_allows_long_4h_hedge_inside_daily_short():
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
                close=Decimal("63000"),
                fast_ma=Decimal("63500"),
                slow_ma=Decimal("65000"),
                fast_ma_slope=Decimal("-100"),
                adx=Decimal("22"),
                di_plus=Decimal("18"),
                di_minus=Decimal("28"),
            ),
            four_hour=TrendSnapshot(
                close=Decimal("64200"),
                fast_ma=Decimal("64000"),
                slow_ma=Decimal("63200"),
                fast_ma_slope=Decimal("90"),
                adx=Decimal("24"),
                di_plus=Decimal("30"),
                di_minus=Decimal("16"),
            ),
            one_hour=TrendSnapshot(
                close=Decimal("64400"),
                fast_ma=Decimal("64100"),
                slow_ma=Decimal("63400"),
                fast_ma_slope=Decimal("70"),
                adx=Decimal("23"),
                di_plus=Decimal("29"),
                di_minus=Decimal("15"),
            ),
            entry=LayeredEntryFrame(
                close=Decimal("64600"),
                open=Decimal("64200"),
                high=Decimal("64700"),
                low=Decimal("63900"),
                fast_ma=Decimal("64100"),
                atr=Decimal("350"),
                recent_swing_low=Decimal("63600"),
                recent_swing_high=Decimal("65000"),
            ),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is not None
    assert decision.signal.strategy_type == "LONG_4H_HEDGE"
    assert decision.signal.action == "LONG_ENTRY"
    assert decision.signal.bucket == "FOUR_HOUR_HEDGE"
    assert decision.signal.risk_pct == Decimal("0.002")


def test_layered_strategy_allows_short_4h_hedge_inside_daily_long():
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
                close=Decimal("70000"),
                fast_ma=Decimal("69000"),
                slow_ma=Decimal("66000"),
                fast_ma_slope=Decimal("150"),
                adx=Decimal("25"),
                di_plus=Decimal("32"),
                di_minus=Decimal("14"),
            ),
            four_hour=TrendSnapshot(
                close=Decimal("68000"),
                fast_ma=Decimal("68100"),
                slow_ma=Decimal("69000"),
                fast_ma_slope=Decimal("-120"),
                adx=Decimal("24"),
                di_plus=Decimal("15"),
                di_minus=Decimal("30"),
            ),
            one_hour=TrendSnapshot(
                close=Decimal("67600"),
                fast_ma=Decimal("67800"),
                slow_ma=Decimal("68600"),
                fast_ma_slope=Decimal("-80"),
                adx=Decimal("23"),
                di_plus=Decimal("16"),
                di_minus=Decimal("28"),
            ),
            entry=LayeredEntryFrame(
                close=Decimal("67400"),
                open=Decimal("67900"),
                high=Decimal("68200"),
                low=Decimal("67300"),
                fast_ma=Decimal("67800"),
                atr=Decimal("400"),
                recent_swing_low=Decimal("67000"),
                recent_swing_high=Decimal("68400"),
            ),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is not None
    assert decision.signal.strategy_type == "SHORT_4H_HEDGE"
    assert decision.signal.action == "SHORT_ENTRY"
    assert decision.signal.bucket == "FOUR_HOUR_HEDGE"


def test_layered_strategy_reports_bearish_trend_details_when_momentum_filter_blocks_signal():
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
                close=Decimal("62000"),
                fast_ma=Decimal("64000"),
                slow_ma=Decimal("66000"),
                fast_ma_slope=Decimal("-200"),
                adx=Decimal("12"),
                di_plus=Decimal("25"),
                di_minus=Decimal("20"),
            ),
            four_hour=TrendSnapshot(
                close=Decimal("61800"),
                fast_ma=Decimal("62500"),
                slow_ma=Decimal("64000"),
                fast_ma_slope=Decimal("-150"),
                adx=Decimal("24"),
                di_plus=Decimal("14"),
                di_minus=Decimal("31"),
            ),
            one_hour=TrendSnapshot(
                close=Decimal("61750"),
                fast_ma=Decimal("62200"),
                slow_ma=Decimal("63500"),
                fast_ma_slope=Decimal("-80"),
                adx=Decimal("23"),
                di_plus=Decimal("16"),
                di_minus=Decimal("29"),
            ),
            entry=LayeredEntryFrame(
                close=Decimal("61600"),
                open=Decimal("62100"),
                high=Decimal("62300"),
                low=Decimal("61500"),
                fast_ma=Decimal("62000"),
                atr=Decimal("300"),
                recent_swing_low=Decimal("61000"),
                recent_swing_high=Decimal("62800"),
            ),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is None
    assert "SHORT_DAY_CORE" in decision.candidates
    statuses = {
        str(item["text"]): item
        for item in decision.diagnostics
        if item.get("strategy") == "SHORT_DAY_CORE"
    }
    assert statuses["日线空头基础"]["passed"] is True
    assert statuses["日线空头斜率"]["passed"] is True
    assert statuses["日线空头动能"]["passed"] is False
    assert "ADX=12" in str(statuses["日线空头动能"]["detail"])
    assert "DI-=20" in str(statuses["日线空头动能"]["detail"])


def test_layered_strategy_keeps_confirmed_daily_short_regime_when_current_momentum_cools():
    from app.strategy.layered_strategy import (
        LayeredEntryFrame,
        LayeredStrategyConfig,
        LayeredStrategyInput,
        TrendRegime,
        TrendSnapshot,
        build_layered_strategy_decision,
    )

    decision = build_layered_strategy_decision(
        LayeredStrategyInput(
            symbol="BTCUSDT",
            daily=TrendSnapshot(
                close=Decimal("62000"),
                fast_ma=Decimal("64000"),
                slow_ma=Decimal("66000"),
                fast_ma_slope=Decimal("-200"),
                adx=Decimal("12"),
                di_plus=Decimal("25"),
                di_minus=Decimal("20"),
            ),
            four_hour=TrendSnapshot(
                close=Decimal("61800"),
                fast_ma=Decimal("62500"),
                slow_ma=Decimal("64000"),
                fast_ma_slope=Decimal("-150"),
                adx=Decimal("24"),
                di_plus=Decimal("14"),
                di_minus=Decimal("31"),
            ),
            one_hour=TrendSnapshot(
                close=Decimal("61750"),
                fast_ma=Decimal("62200"),
                slow_ma=Decimal("63500"),
                fast_ma_slope=Decimal("-80"),
                adx=Decimal("23"),
                di_plus=Decimal("16"),
                di_minus=Decimal("29"),
            ),
            entry=LayeredEntryFrame(
                close=Decimal("61600"),
                open=Decimal("62100"),
                high=Decimal("62300"),
                low=Decimal("61500"),
                fast_ma=Decimal("62000"),
                atr=Decimal("300"),
                recent_swing_low=Decimal("61000"),
                recent_swing_high=Decimal("62800"),
            ),
            daily_regime=TrendRegime(direction="SHORT", confirmed_at_ms=1000),
            four_hour_regime=TrendRegime(direction="SHORT", confirmed_at_ms=2000),
            one_hour_regime=TrendRegime(direction="SHORT", confirmed_at_ms=3000),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is not None
    assert decision.signal.strategy_type == "SHORT_DAY_CORE"
    assert "SHORT_DAY_CORE" in decision.candidates
    statuses = {
        str(item["text"]): item
        for item in decision.diagnostics
        if item.get("strategy") == "SHORT_DAY_CORE"
    }
    assert statuses["日线空头已确认"]["passed"] is True
    assert statuses["当前日线空头动能"]["passed"] is False
    assert statuses["当前日线空头动能"]["required"] is False


def test_layered_strategy_flips_daily_short_to_long_only_after_daily_long_regime_confirms():
    from app.strategy.layered_strategy import (
        LayeredEntryFrame,
        LayeredStrategyConfig,
        LayeredStrategyInput,
        TrendRegime,
        TrendSnapshot,
        build_layered_strategy_decision,
    )

    decision = build_layered_strategy_decision(
        LayeredStrategyInput(
            symbol="BTCUSDT",
            daily=TrendSnapshot(
                close=Decimal("70000"),
                fast_ma=Decimal("69000"),
                slow_ma=Decimal("66000"),
                fast_ma_slope=Decimal("150"),
                adx=Decimal("25"),
                di_plus=Decimal("32"),
                di_minus=Decimal("14"),
            ),
            four_hour=TrendSnapshot(
                close=Decimal("70400"),
                fast_ma=Decimal("70000"),
                slow_ma=Decimal("68000"),
                fast_ma_slope=Decimal("120"),
                adx=Decimal("24"),
                di_plus=Decimal("31"),
                di_minus=Decimal("15"),
            ),
            one_hour=TrendSnapshot(
                close=Decimal("70600"),
                fast_ma=Decimal("70200"),
                slow_ma=Decimal("68400"),
                fast_ma_slope=Decimal("90"),
                adx=Decimal("23"),
                di_plus=Decimal("30"),
                di_minus=Decimal("16"),
            ),
            entry=LayeredEntryFrame(
                close=Decimal("70800"),
                open=Decimal("70400"),
                high=Decimal("70900"),
                low=Decimal("70300"),
                fast_ma=Decimal("70500"),
                atr=Decimal("400"),
                recent_swing_low=Decimal("69800"),
                recent_swing_high=Decimal("71000"),
            ),
            daily_regime=TrendRegime(direction="LONG", confirmed_at_ms=4000),
            four_hour_regime=TrendRegime(direction="LONG", confirmed_at_ms=4100),
            one_hour_regime=TrendRegime(direction="LONG", confirmed_at_ms=4200),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is not None
    assert decision.signal.strategy_type == "LONG_DAY_CORE"
    assert "LONG_DAY_CORE" in decision.candidates
