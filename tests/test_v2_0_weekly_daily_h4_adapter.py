from decimal import Decimal

from app.data.quality import INTERVAL_MS, Kline


def _series(symbol: str, interval: str, start: Decimal, step: Decimal, count: int = 90) -> tuple[Kline, ...]:
    rows = []
    interval_ms = INTERVAL_MS[interval]
    for index in range(count):
        close = start + step * Decimal(index)
        open_time = index * interval_ms
        rows.append(
            Kline(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + interval_ms - 1,
                open=close + Decimal("1"),
                high=close + Decimal("2"),
                low=close - Decimal("2"),
                close=close,
                volume=Decimal("100"),
            )
        )
    return tuple(rows)


def test_realtime_adapter_uses_weekly_daily_h4_kernel_without_old_layered_switch():
    from app.paper.multitimeframe import MultiTimeframeFrame
    from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal

    frame = MultiTimeframeFrame(
        symbol="BTCUSDT",
        klines_by_interval={
            "1w": _series("BTCUSDT", "1w", Decimal("200"), Decimal("-1")),
            "1d": _series("BTCUSDT", "1d", Decimal("190"), Decimal("-1")),
            "4h": _series("BTCUSDT", "4h", Decimal("180"), Decimal("-1")),
        },
    )

    signal = build_realtime_strategy_signal(frame, RealtimeStrategyConfig())

    assert signal.strategy_kernel == "WEEKLY_DAILY_H4_V1"
    assert signal.position_level == "WEEKLY"
    assert signal.strategy_type.startswith("WEEKLY_")
    assert signal.bucket == "WEEKLY"
