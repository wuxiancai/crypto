from decimal import Decimal

from app.data.quality import INTERVAL_MS, Kline
from app.strategy.signal_router import StrategySignal


def _kline(symbol: str, interval: str, open_time: int, close: str = "100") -> Kline:
    value = Decimal(close)
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=open_time,
        close_time=open_time + INTERVAL_MS[interval] - 1,
        open=value,
        high=value + Decimal("1"),
        low=value - Decimal("1"),
        close=value,
        volume=Decimal("10"),
        is_closed=True,
    )


def test_layered_history_probe_scans_until_expected_signal(monkeypatch):
    import scripts.validate_layered_btc_history as validation

    symbol = "BTCUSDT"
    klines = []
    for index in range(70):
        klines.append(_kline(symbol, "1d", index * INTERVAL_MS["1d"]))
        klines.append(_kline(symbol, "4h", index * INTERVAL_MS["4h"]))
        klines.append(_kline(symbol, "1h", index * INTERVAL_MS["1h"]))
    base_time = 69 * INTERVAL_MS["1d"]
    for index in range(12):
        klines.append(_kline(symbol, "15m", base_time + index * INTERVAL_MS["15m"], close=str(100 + index)))

    target_open_time = base_time + 6 * INTERVAL_MS["15m"]

    def fake_signal(frame, _config):
        latest_15m = frame.latest("15m")
        if latest_15m.open_time >= target_open_time:
            return StrategySignal(
                action="SELL",
                strategy_type="SHORT_DAY_CORE",
                bucket="DAY_CORE",
                reason=["matched synthetic short"],
                entry_price=latest_15m.close,
            )
        return StrategySignal(action="WAIT", strategy_type="SYSTEM", reason=["not yet"])

    monkeypatch.setattr(validation, "build_realtime_strategy_signal", fake_signal)

    probe = validation.LayeredHistoryProbe(
        name="synthetic_short",
        start_time="1970-03-11 08:00:00+08:00",
        end_time="1970-03-11 12:00:00+08:00",
        expected_strategy="SHORT_DAY_CORE",
        expected_action="SELL",
    )
    result = validation.evaluate_layered_history_probe(klines=klines, probe=probe)

    assert result.matched is True
    assert result.matched_strategy == "SHORT_DAY_CORE"
    assert result.matched_action == "SELL"
    assert result.matched_bucket == "DAY_CORE"
    assert result.checked_15m_bars == 7


def test_layered_history_probe_reports_last_signal_when_no_match(monkeypatch):
    import scripts.validate_layered_btc_history as validation

    symbol = "BTCUSDT"
    klines = []
    for index in range(70):
        klines.append(_kline(symbol, "1d", index * INTERVAL_MS["1d"]))
        klines.append(_kline(symbol, "4h", index * INTERVAL_MS["4h"]))
        klines.append(_kline(symbol, "1h", index * INTERVAL_MS["1h"]))
    base_time = 69 * INTERVAL_MS["1d"]
    for index in range(4):
        klines.append(_kline(symbol, "15m", base_time + index * INTERVAL_MS["15m"]))

    def fake_signal(_frame, _config):
        return StrategySignal(action="WAIT", strategy_type="SYSTEM", reason=["no setup"])

    monkeypatch.setattr(validation, "build_realtime_strategy_signal", fake_signal)

    probe = validation.LayeredHistoryProbe(
        name="synthetic_no_match",
        start_time="1970-03-11 08:00:00+08:00",
        end_time="1970-03-11 09:00:00+08:00",
        expected_strategy="LONG_4H_HEDGE",
        expected_action="BUY",
    )
    result = validation.evaluate_layered_history_probe(klines=klines, probe=probe)

    assert result.matched is False
    assert result.checked_15m_bars == 4
    assert result.last_strategy == "SYSTEM"
    assert result.last_reason == ["no setup"]


def test_default_btc_probes_cover_transition_core_and_hedge():
    import scripts.validate_layered_btc_history as validation

    assert [probe.name for probe in validation.DEFAULT_BTC_PROBES] == [
        "btc_2026_4h_short_transition",
        "btc_2026_daily_short_core",
        "btc_2026_4h_rebound_hedge",
    ]
    assert [probe.expected_strategy for probe in validation.DEFAULT_BTC_PROBES] == [
        "SHORT_4H_HEDGE",
        "SHORT_DAY_CORE",
        "LONG_4H_HEDGE",
    ]
