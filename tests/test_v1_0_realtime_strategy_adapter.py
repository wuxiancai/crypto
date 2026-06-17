from decimal import Decimal


def _kline(symbol: str, interval: str, index: int, close: str):
    from app.data.quality import INTERVAL_MS, Kline

    open_time = index * INTERVAL_MS[interval]
    price = Decimal(close)
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=open_time,
        close_time=open_time + INTERVAL_MS[interval] - 1,
        open=price,
        high=price + Decimal("2"),
        low=price - Decimal("2"),
        close=price,
        volume=Decimal("10"),
    )


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
            "15m": tuple(
                _kline("BTCUSDT", "15m", index, close)
                for index, close in enumerate(["120", "124", "128", "124", "126"])
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


def test_realtime_strategy_builds_reversal_long_signal_when_4h_down_and_1h_turns_up():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "4h": tuple(
                _kline("BTCUSDT", "4h", index, close)
                for index, close in enumerate(["120", "110", "100", "90", "82", "80"])
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
