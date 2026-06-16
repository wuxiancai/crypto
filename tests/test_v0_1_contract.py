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
    from app.indicators.core import atr, bollinger_bands, ema

    closes = [Decimal(value) for value in ["10", "11", "12", "13", "14"]]

    assert ema(closes, period=3)[-1].quantize(Decimal("0.0001")) == Decimal("13.0625")

    bands = bollinger_bands(closes, period=5, stddev=Decimal("2"))
    assert bands[-1].middle == Decimal("12")
    assert bands[-1].upper > bands[-1].middle
    assert bands[-1].lower < bands[-1].middle

    highs = [Decimal("11"), Decimal("12"), Decimal("13")]
    lows = [Decimal("9"), Decimal("10"), Decimal("11")]
    closes_for_atr = [Decimal("10"), Decimal("11"), Decimal("12")]
    assert atr(highs, lows, closes_for_atr, period=3)[-1] == Decimal("2")

