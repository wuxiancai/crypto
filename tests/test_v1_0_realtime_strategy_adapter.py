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
