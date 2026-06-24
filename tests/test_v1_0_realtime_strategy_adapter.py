from decimal import Decimal


def _kline(
    symbol: str,
    interval: str,
    index: int,
    close: str,
    open_price: str | None = None,
    high: str | None = None,
    low: str | None = None,
):
    from app.data.quality import INTERVAL_MS, Kline

    open_time = index * INTERVAL_MS[interval]
    price = Decimal(close)
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=open_time,
        close_time=open_time + INTERVAL_MS[interval] - 1,
        open=Decimal(open_price) if open_price is not None else price,
        high=Decimal(high) if high is not None else price + Decimal("2"),
        low=Decimal(low) if low is not None else price - Decimal("2"),
        close=price,
        volume=Decimal("10"),
    )


def _klines(symbol: str, interval: str, closes: list[str]):
    return tuple(_kline(symbol, interval, index, close) for index, close in enumerate(closes))


def test_realtime_strategy_waits_until_indicator_history_is_ready():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "15m": (_kline("BTCUSDT", "15m", 0, "100"),),
            "1h": (_kline("BTCUSDT", "1h", 0, "100"),),
            "4h": (_kline("BTCUSDT", "4h", 0, "100"),),
        },
    )

    signal = build_realtime_strategy_signal(
        frame,
        config=RealtimeStrategyConfig(
            ema_fast_period=3,
            ema_slow_period=5,
            atr_period=3,
            dmi_period=3,
            swing_lookback=5,
        ),
    )

    assert signal.action == "WAIT"
    assert signal.strategy_type == "SYSTEM"
    assert signal.reason == ["not enough closed klines for realtime indicators"]


def test_realtime_strategy_builds_trend_pullback_long_signal_from_multitimeframe_klines():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "4h": tuple(
                _kline("BTCUSDT", "4h", index, close)
                for index, close in enumerate(["100", "104", "108", "112", "116", "120"])
            ),
            "1h": tuple(
                _kline("BTCUSDT", "1h", index, close)
                for index, close in enumerate(["108", "112", "116", "120", "124", "128"])
            ),
            "15m": (
                *_klines("BTCUSDT", "15m", ["120", "124", "128", "124"]),
                _kline("BTCUSDT", "15m", 4, "126", open_price="125"),
            ),
        },
    )

    signal = build_realtime_strategy_signal(
        frame,
        config=RealtimeStrategyConfig(
            ema_fast_period=3,
            ema_slow_period=5,
            atr_period=3,
            dmi_period=3,
            swing_lookback=5,
        ),
    )

    assert signal.action == "LONG_ENTRY"
    assert signal.strategy_type == "TREND_PULLBACK"
    assert signal.entry_price == Decimal("126")
    assert signal.stop_loss == Decimal("118")
    assert signal.take_profit == Decimal("142")
    assert set(signal.chart_timeframes) == {"4h", "1h", "15m"}
    assert signal.chart_timeframes["4h"][0]["open"] == "100"
    assert signal.chart_timeframes["1h"][0]["open"] == "108"
    assert signal.chart_timeframes["15m"][0]["open"] == "120"


def test_realtime_strategy_uses_layered_strategy_when_daily_history_is_present():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "1d": tuple(
                _kline("BTCUSDT", "1d", index, close)
                for index, close in enumerate(["130", "125", "120", "115", "110", "105"])
            ),
            "4h": tuple(
                _kline("BTCUSDT", "4h", index, close)
                for index, close in enumerate(["120", "116", "112", "108", "104", "100"])
            ),
            "1h": tuple(
                _kline("BTCUSDT", "1h", index, close)
                for index, close in enumerate(["114", "110", "106", "102", "98", "94"])
            ),
            "15m": (
                *_klines("BTCUSDT", "15m", ["104", "102", "100", "98"]),
                _kline("BTCUSDT", "15m", 4, "96", open_price="99", high="100", low="95"),
            ),
        },
    )

    signal = build_realtime_strategy_signal(
        frame,
        config=RealtimeStrategyConfig(
            ema_fast_period=3,
            ema_slow_period=5,
            atr_period=3,
            dmi_period=3,
            swing_lookback=5,
            enable_layered_strategy=True,
        ),
    )

    assert signal.action == "SHORT_ENTRY"
    assert signal.strategy_type == "SHORT_DAY_CORE"
    assert signal.bucket == "DAY_CORE"
    assert "1d" in signal.chart_timeframes


def test_realtime_strategy_regime_keeps_daily_short_until_opposite_momentum_confirms():
    from app.paper.strategy_adapter import RealtimeStrategyConfig, _trend_regime_from_snapshots
    from app.strategy.layered_strategy import TrendSnapshot

    config = RealtimeStrategyConfig(min_adx=Decimal("20"))
    regime = _trend_regime_from_snapshots(
        [
            (
                1_000,
                TrendSnapshot(
                    close=Decimal("66000"),
                    fast_ma=Decimal("64000"),
                    slow_ma=Decimal("66000"),
                    fast_ma_slope=Decimal("-100"),
                    adx=Decimal("25"),
                    di_plus=Decimal("15"),
                    di_minus=Decimal("30"),
                ),
            ),
            (
                2_000,
                TrendSnapshot(
                    close=Decimal("68000"),
                    fast_ma=Decimal("67000"),
                    slow_ma=Decimal("66000"),
                    fast_ma_slope=Decimal("100"),
                    adx=Decimal("12"),
                    di_plus=Decimal("30"),
                    di_minus=Decimal("15"),
                ),
            ),
        ],
        config,
    )

    assert regime.direction == "SHORT"
    assert regime.confirmed_at_ms == 1_000


def test_realtime_strategy_regime_flips_to_daily_long_after_opposite_momentum_confirms():
    from app.paper.strategy_adapter import RealtimeStrategyConfig, _trend_regime_from_snapshots
    from app.strategy.layered_strategy import TrendSnapshot

    config = RealtimeStrategyConfig(min_adx=Decimal("20"))
    regime = _trend_regime_from_snapshots(
        [
            (
                1_000,
                TrendSnapshot(
                    close=Decimal("66000"),
                    fast_ma=Decimal("64000"),
                    slow_ma=Decimal("66000"),
                    fast_ma_slope=Decimal("-100"),
                    adx=Decimal("25"),
                    di_plus=Decimal("15"),
                    di_minus=Decimal("30"),
                ),
            ),
            (
                2_000,
                TrendSnapshot(
                    close=Decimal("70000"),
                    fast_ma=Decimal("69000"),
                    slow_ma=Decimal("66000"),
                    fast_ma_slope=Decimal("150"),
                    adx=Decimal("24"),
                    di_plus=Decimal("32"),
                    di_minus=Decimal("14"),
                ),
            ),
        ],
        config,
    )

    assert regime.direction == "LONG"
    assert regime.confirmed_at_ms == 2_000


def test_realtime_strategy_builds_reversal_long_signal_when_4h_down_and_1h_turns_up():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "4h": tuple(
                _kline("BTCUSDT", "4h", index, close)
                for index, close in enumerate(["120", "110", "100", "90", "80", "81"])
            ),
            "1h": tuple(
                _kline("BTCUSDT", "1h", index, close)
                for index, close in enumerate(["80", "84", "88", "92", "96", "100"])
            ),
            "15m": tuple(
                _kline("BTCUSDT", "15m", index, close)
                for index, close in enumerate(["90", "94", "98", "96", "97", "98"])
            ),
        },
    )

    signal = build_realtime_strategy_signal(
        frame,
        config=RealtimeStrategyConfig(
            ema_fast_period=3,
            ema_slow_period=5,
            atr_period=3,
            dmi_period=3,
            swing_lookback=5,
        ),
    )

    assert signal.action == "REVERSAL_LONG_ENTRY"
    assert signal.strategy_type == "REVERSAL_PROBE"
    assert signal.signal_level == "EARLY"
    assert signal.risk_pct == Decimal("0.002")
    assert signal.entry_price == Decimal("98")
    assert signal.stop_loss is not None
    assert signal.take_profit is not None


def test_realtime_strategy_reports_trigger_conditions_and_nearest_strategy():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "4h": tuple(
                _kline("BTCUSDT", "4h", index, close)
                for index, close in enumerate(["100", "104", "108", "112", "116", "120"])
            ),
            "1h": tuple(
                _kline("BTCUSDT", "1h", index, close)
                for index, close in enumerate(["108", "112", "116", "120", "124", "128"])
            ),
            "15m": (
                *_klines("BTCUSDT", "15m", ["120", "124", "128", "124"]),
                _kline("BTCUSDT", "15m", 4, "126", open_price="125"),
            ),
        },
    )

    signal = build_realtime_strategy_signal(
        frame,
        config=RealtimeStrategyConfig(
            ema_fast_period=3,
            ema_slow_period=5,
            atr_period=3,
            dmi_period=3,
            swing_lookback=5,
        ),
    )

    assert signal.nearest_strategy["name"] == "主趋势做多"
    assert signal.nearest_strategy["matched"] == signal.nearest_strategy["total"]
    assert {
        condition["text"]
        for condition in signal.condition_statuses
        if condition["strategy"] == "主趋势做多"
    } >= {
        "4h 多头结构",
        "4h 多头动能确认",
        "1h 多头结构",
        "1h 多头动能确认",
        "15m 回踩到 EMA50 区域",
        "15m 看涨确认",
        "止损有效",
        "风险收益比达标",
    }
    assert all(
        condition["passed"]
        for condition in signal.condition_statuses
        if condition["strategy"] == "主趋势做多"
    )


def test_realtime_strategy_can_use_ma_for_slow_average_in_diagnostics():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "4h": tuple(
                _kline("BTCUSDT", "4h", index, close)
                for index, close in enumerate(["100", "104", "108", "112", "116", "120"])
            ),
            "1h": tuple(
                _kline("BTCUSDT", "1h", index, close)
                for index, close in enumerate(["108", "112", "116", "120", "124", "128"])
            ),
            "15m": (
                *_klines("BTCUSDT", "15m", ["120", "124", "128", "124"]),
                _kline("BTCUSDT", "15m", 4, "126", open_price="125"),
            ),
        },
    )

    signal = build_realtime_strategy_signal(
        frame,
        config=RealtimeStrategyConfig(
            fast_ma_type="EMA",
            slow_ma_type="MA",
            ema_fast_period=3,
            ema_slow_period=5,
            atr_period=3,
            dmi_period=3,
            swing_lookback=5,
        ),
    )

    assert any("EMA3 > MA5" in rule for rule in signal.core_rules)
    assert signal.chart_timeframes["15m"][-1]["ema200"] == "124.4"


def test_realtime_strategy_reports_bearish_structure_separately_from_momentum_confirmation():
    from app.paper.strategy_adapter import RealtimeStrategyConfig, _main_short_conditions
    from app.strategy.pullback_strategy import EntryFrame
    from app.strategy.trend_detector import TrendFrame

    config = RealtimeStrategyConfig(min_adx=Decimal("20"))
    four_hour = TrendFrame(
        close=Decimal("1742"),
        ema50=Decimal("1733"),
        ema200=Decimal("1860"),
        ema50_slope=Decimal("25"),
        di_plus=Decimal("20"),
        di_minus=Decimal("14"),
        adx=Decimal("37"),
    )
    one_hour = TrendFrame(
        close=Decimal("62441"),
        ema50=Decimal("64075"),
        ema200=Decimal("64812"),
        ema50_slope=Decimal("-10"),
        di_plus=Decimal("15"),
        di_minus=Decimal("27"),
        adx=Decimal("22"),
    )
    entry_frame = EntryFrame(
        close=Decimal("62746"),
        previous_close=Decimal("64578"),
        ema50=Decimal("64430"),
        atr=Decimal("450"),
        recent_swing_low=Decimal("62369"),
        recent_swing_high=Decimal("64607"),
    )

    conditions = _main_short_conditions(four_hour, one_hour, entry_frame, config)

    by_text = {condition["text"]: condition for condition in conditions}
    assert "4h 下跌趋势" not in by_text
    assert by_text["4h 空头结构"]["passed"] is True
    assert by_text["4h 空头动能确认"]["passed"] is False
    assert by_text["1h 空头结构"]["passed"] is True
    assert by_text["1h 空头动能确认"]["passed"] is True


def test_nearest_strategy_prioritizes_primary_four_hour_structure_over_match_count():
    from app.paper.strategy_adapter import _nearest_strategy

    conditions = [
        {"strategy": "主趋势做多", "text": "4h 多头结构", "passed": False, "detail": ""},
        {"strategy": "主趋势做多", "text": "4h 多头动能确认", "passed": False, "detail": ""},
        {"strategy": "主趋势做多", "text": "1h 多头结构", "passed": True, "detail": ""},
        {"strategy": "主趋势做多", "text": "1h 多头动能确认", "passed": False, "detail": ""},
        {"strategy": "主趋势做多", "text": "15m 回踩到 EMA50 区域", "passed": True, "detail": ""},
        {"strategy": "主趋势做多", "text": "15m 看涨确认", "passed": True, "detail": ""},
        {"strategy": "主趋势做多", "text": "止损有效", "passed": True, "detail": ""},
        {"strategy": "主趋势做多", "text": "风险收益比达标", "passed": True, "detail": ""},
        {"strategy": "主趋势做空", "text": "4h 空头结构", "passed": True, "detail": ""},
        {"strategy": "主趋势做空", "text": "4h 空头动能确认", "passed": False, "detail": ""},
        {"strategy": "主趋势做空", "text": "1h 空头结构", "passed": True, "detail": ""},
        {"strategy": "主趋势做空", "text": "1h 空头动能确认", "passed": False, "detail": ""},
        {"strategy": "主趋势做空", "text": "15m 反弹到 EMA50 区域", "passed": False, "detail": ""},
        {"strategy": "主趋势做空", "text": "15m 看跌确认", "passed": False, "detail": ""},
        {"strategy": "主趋势做空", "text": "止损有效", "passed": True, "detail": ""},
        {"strategy": "主趋势做空", "text": "风险收益比达标", "passed": True, "detail": ""},
    ]

    nearest = _nearest_strategy(conditions)

    assert nearest["name"] == "主趋势做空"
    assert nearest["matched"] == 4
    assert nearest["total"] == 8
