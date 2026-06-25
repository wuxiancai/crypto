from datetime import datetime, timezone
from decimal import Decimal

import pytest


def test_live_mode_requires_explicit_confirmation(monkeypatch):
    from app.config.settings import Settings

    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)

    with pytest.raises(ValueError, match="LIVE_TRADING_CONFIRM"):
        Settings(environment="live", execution_mode="live")


def test_validates_closed_kline_sequence_and_ohlc_rules():
    from app.data.quality import Kline, validate_kline_sequence

    rows = [
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=0,
            close_time=899_999,
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("95"),
            close=Decimal("105"),
            volume=Decimal("10"),
            is_closed=True,
        ),
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("105"),
            high=Decimal("106"),
            low=Decimal("90"),
            close=Decimal("95"),
            volume=Decimal("8"),
            is_closed=True,
        ),
    ]

    assert validate_kline_sequence(rows) == []

    broken = rows.copy()
    broken[1] = broken[1].model_copy(update={"open_time": 1_800_000})

    errors = validate_kline_sequence(broken)
    assert any("not continuous" in error for error in errors)


def test_multi_timeframe_context_uses_only_closed_klines():
    from app.data.timeframes import closed_window_open_time

    current_time = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)

    assert closed_window_open_time(current_time, "15m") == datetime(
        2026, 1, 1, 10, 0, tzinfo=timezone.utc
    )
    assert closed_window_open_time(current_time, "1h") == datetime(
        2026, 1, 1, 9, 0, tzinfo=timezone.utc
    )
    assert closed_window_open_time(current_time, "4h") == datetime(
        2026, 1, 1, 4, 0, tzinfo=timezone.utc
    )


def test_indicators_compute_expected_values_for_simple_series():
    from app.indicators.core import atr, bollinger_bands, ema, ma

    closes = [Decimal(value) for value in ["10", "11", "12", "13", "14"]]

    assert ema(closes, period=3)[-1].quantize(Decimal("0.0001")) == Decimal("13.0625")
    assert ma(closes, period=3) == [None, None, Decimal("11"), Decimal("12"), Decimal("13")]

    bands = bollinger_bands(closes, period=5, stddev=Decimal("2"))
    assert bands[-1].middle == Decimal("12")
    assert bands[-1].upper > bands[-1].middle
    assert bands[-1].lower < bands[-1].middle

    highs = [Decimal("11"), Decimal("12"), Decimal("13")]
    lows = [Decimal("9"), Decimal("10"), Decimal("11")]
    closes_for_atr = [Decimal("10"), Decimal("11"), Decimal("12")]
    assert atr(highs, lows, closes_for_atr, period=3)[-1] == Decimal("2")


def test_atr_uses_wilder_smoothing_after_initial_seed():
    from app.indicators.core import atr

    highs = [Decimal("10"), Decimal("12"), Decimal("15"), Decimal("19")]
    lows = [Decimal("9"), Decimal("10"), Decimal("12"), Decimal("15")]
    closes = [Decimal("9.5"), Decimal("11"), Decimal("13"), Decimal("16")]

    values = atr(highs, lows, closes, period=3)

    assert values[:2] == [None, None]
    assert values[2].quantize(Decimal("0.0001")) == Decimal("2.5000")
    assert values[3].quantize(Decimal("0.0001")) == Decimal("3.6667")


def test_directional_movement_identifies_uptrend_and_downtrend_direction():
    from app.indicators.core import directional_movement_index

    up = directional_movement_index(
        highs=[Decimal("10"), Decimal("11"), Decimal("12"), Decimal("13"), Decimal("14")],
        lows=[Decimal("8"), Decimal("9"), Decimal("10"), Decimal("11"), Decimal("12")],
        closes=[Decimal("9"), Decimal("10"), Decimal("11"), Decimal("12"), Decimal("13")],
        period=3,
    )
    assert up[-1] is not None
    assert up[-1].di_plus > up[-1].di_minus
    assert up[-1].adx > 0

    down = directional_movement_index(
        highs=[Decimal("14"), Decimal("13"), Decimal("12"), Decimal("11"), Decimal("10")],
        lows=[Decimal("12"), Decimal("11"), Decimal("10"), Decimal("9"), Decimal("8")],
        closes=[Decimal("13"), Decimal("12"), Decimal("11"), Decimal("10"), Decimal("9")],
        period=3,
    )
    assert down[-1] is not None
    assert down[-1].di_minus > down[-1].di_plus
    assert down[-1].adx > 0


def test_directional_movement_waits_for_wilder_adx_seed_window():
    from app.indicators.core import directional_movement_index

    up = directional_movement_index(
        highs=[Decimal(value) for value in ["10", "11", "12", "13", "14"]],
        lows=[Decimal(value) for value in ["8", "9", "10", "11", "12"]],
        closes=[Decimal(value) for value in ["9", "10", "11", "12", "13"]],
        period=3,
    )

    assert up[:4] == [None, None, None, None]
    assert up[4] is not None
    assert up[4].adx == Decimal("100")
