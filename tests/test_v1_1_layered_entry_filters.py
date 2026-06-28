from decimal import Decimal

from app.strategy.layered_strategy import (
    DAY_CORE,
    LayeredEntryFrame,
    LayeredStrategyConfig,
    LayeredStrategyInput,
    TrendRegime,
    TrendSnapshot,
    build_layered_strategy_decision,
)


def _snapshot(direction: str, *, close: str | None = None, slope: str | None = None) -> TrendSnapshot:
    if direction == "SHORT":
        return TrendSnapshot(
            close=Decimal(close or "61800"),
            fast_ma=Decimal("62500"),
            slow_ma=Decimal("64000"),
            fast_ma_slope=Decimal(slope or "-150"),
            adx=Decimal("24"),
            di_plus=Decimal("14"),
            di_minus=Decimal("31"),
        )
    return TrendSnapshot(
        close=Decimal(close or "70400"),
        fast_ma=Decimal("70000"),
        slow_ma=Decimal("68000"),
        fast_ma_slope=Decimal(slope or "120"),
        adx=Decimal("24"),
        di_plus=Decimal("31"),
        di_minus=Decimal("15"),
    )


def _short_input(*, four_hour_close: str = "61800", four_hour_slope: str = "-150", one_hour_slope: str = "-80", entry_close: str = "61600") -> LayeredStrategyInput:
    return LayeredStrategyInput(
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
        four_hour=_snapshot("SHORT", close=four_hour_close, slope=four_hour_slope),
        one_hour=TrendSnapshot(
            close=Decimal("61750"),
            fast_ma=Decimal("62200"),
            slow_ma=Decimal("63500"),
            fast_ma_slope=Decimal(one_hour_slope),
            adx=Decimal("23"),
            di_plus=Decimal("16"),
            di_minus=Decimal("29"),
        ),
        entry=LayeredEntryFrame(
            close=Decimal(entry_close),
            open=Decimal("62100"),
            high=Decimal("62300"),
            low=Decimal("61500"),
            fast_ma=Decimal("62000"),
            atr=Decimal("300"),
            recent_swing_low=Decimal("61000"),
            recent_swing_high=Decimal("62800"),
        ),
        daily_regime=TrendRegime("SHORT", 1000),
        four_hour_regime=TrendRegime("SHORT", 2000),
        one_hour_regime=TrendRegime("SHORT", 3000),
    )


def test_short_entry_blocked_when_4h_price_is_above_fast_ma_even_if_regime_is_short():
    decision = build_layered_strategy_decision(
        _short_input(four_hour_close="62600"),
        LayeredStrategyConfig(),
    )

    assert decision.signal is None
    statuses = {
        str(item["text"]): item
        for item in decision.diagnostics
        if item.get("strategy") == "SHORT_DAY_CORE"
    }
    assert statuses["4h 空头当前价格未站上快线"]["passed"] is False


def test_short_entry_blocked_when_4h_or_1h_current_slope_turns_up_even_if_regime_is_short():
    four_hour_blocked = build_layered_strategy_decision(
        _short_input(four_hour_slope="120"),
        LayeredStrategyConfig(),
    )
    one_hour_blocked = build_layered_strategy_decision(
        _short_input(one_hour_slope="80"),
        LayeredStrategyConfig(),
    )

    assert four_hour_blocked.signal is None
    assert one_hour_blocked.signal is None


def test_short_entry_reopens_after_4h_reclaims_below_fast_ma_with_down_slopes():
    decision = build_layered_strategy_decision(
        _short_input(four_hour_close="62400", four_hour_slope="-120", one_hour_slope="-60"),
        LayeredStrategyConfig(),
    )

    assert decision.signal is not None
    assert decision.signal.strategy_type == "SHORT_DAY_CORE"


def test_short_addon_uses_same_4h_1h_current_filters():
    strategy_input = _short_input(four_hour_close="62600")
    strategy_input = LayeredStrategyInput(
        symbol=strategy_input.symbol,
        daily=strategy_input.daily,
        four_hour=strategy_input.four_hour,
        one_hour=strategy_input.one_hour,
        entry=strategy_input.entry,
        daily_regime=strategy_input.daily_regime,
        four_hour_regime=strategy_input.four_hour_regime,
        one_hour_regime=strategy_input.one_hour_regime,
        open_buckets=(DAY_CORE,),
        open_strategy_types=("SHORT_DAY_CORE",),
    )

    decision = build_layered_strategy_decision(strategy_input, LayeredStrategyConfig())

    assert decision.signal is None


def test_long_entry_uses_symmetric_filters():
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
                close=Decimal("69900"),
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
            daily_regime=TrendRegime("LONG", 1000),
            four_hour_regime=TrendRegime("LONG", 2000),
            one_hour_regime=TrendRegime("LONG", 3000),
        ),
        LayeredStrategyConfig(),
    )

    assert decision.signal is None
    statuses = {
        str(item["text"]): item
        for item in decision.diagnostics
        if item.get("strategy") == "LONG_DAY_CORE"
    }
    assert statuses["4h 多头当前价格未跌破快线"]["passed"] is False


def test_hedge_entry_uses_15m_confirmation_and_overextension_filters():
    bearish_daily_bullish_lower = LayeredStrategyInput(
        symbol="BTCUSDT",
        daily=_snapshot("SHORT"),
        four_hour=_snapshot("LONG"),
        one_hour=_snapshot("LONG"),
        entry=LayeredEntryFrame(
            close=Decimal("71200"),
            open=Decimal("71100"),
            high=Decimal("71300"),
            low=Decimal("71000"),
            fast_ma=Decimal("70000"),
            atr=Decimal("300"),
            recent_swing_low=Decimal("69000"),
            recent_swing_high=Decimal("71500"),
        ),
        daily_regime=TrendRegime("SHORT", 1000),
        four_hour_regime=TrendRegime("LONG", 2000),
        one_hour_regime=TrendRegime("LONG", 3000),
    )
    long_hedge = build_layered_strategy_decision(
        bearish_daily_bullish_lower,
        LayeredStrategyConfig(),
    )

    bullish_daily_bearish_lower = LayeredStrategyInput(
        symbol="BTCUSDT",
        daily=_snapshot("LONG"),
        four_hour=_snapshot("SHORT"),
        one_hour=_snapshot("SHORT"),
        entry=LayeredEntryFrame(
            close=Decimal("68800"),
            open=Decimal("68900"),
            high=Decimal("69000"),
            low=Decimal("68700"),
            fast_ma=Decimal("70000"),
            atr=Decimal("300"),
            recent_swing_low=Decimal("68500"),
            recent_swing_high=Decimal("71000"),
        ),
        daily_regime=TrendRegime("LONG", 1000),
        four_hour_regime=TrendRegime("SHORT", 2000),
        one_hour_regime=TrendRegime("SHORT", 3000),
    )
    short_hedge = build_layered_strategy_decision(
        bullish_daily_bearish_lower,
        LayeredStrategyConfig(),
    )

    assert long_hedge.signal is None
    assert short_hedge.signal is None
    long_statuses = {
        str(item["text"]): item
        for item in long_hedge.diagnostics
        if item.get("strategy") == "LONG_4H_HEDGE"
    }
    short_statuses = {
        str(item["text"]): item
        for item in short_hedge.diagnostics
        if item.get("strategy") == "SHORT_4H_HEDGE"
    }
    assert long_statuses["15m 多头禁止追多"]["passed"] is False
    assert short_statuses["15m 空头禁止追空"]["passed"] is False
