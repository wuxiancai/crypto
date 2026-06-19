import asyncio
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


def test_strategy_backtest_fetches_history_and_runs_current_realtime_strategy(monkeypatch):
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    requested: list[tuple[str, str, int, int | None, int | None]] = []

    async def fake_fetch_klines(
        symbol: str,
        interval: str,
        limit: int,
        settings=None,
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        requested.append((symbol, interval, limit, start_time, end_time))
        if interval == "4h":
            rows = [
                _kline(symbol, interval, index, close)
                for index, close in zip(range(-6, 0), ["100", "104", "108", "112", "116", "120"])
            ]
        elif interval == "1h":
            rows = [
                _kline(symbol, interval, index, close)
                for index, close in zip(range(-6, 0), ["108", "112", "116", "120", "124", "128"])
            ]
        elif interval == "15m":
            rows = [
                *[
                    _kline(symbol, interval, index, close)
                    for index, close in enumerate(["120", "124", "128", "124"])
                ],
                _kline(symbol, interval, 4, "126", open_price="125"),
                _kline(symbol, interval, 5, "130", open_price="160", high="160", low="125"),
            ]
        else:
            rows = []
        if start_time is None or end_time is None:
            return rows[:limit]
        return [
            row
            for row in rows
            if start_time <= row.open_time <= end_time
        ][:limit]

    monkeypatch.setattr(strategy_backtest, "fetch_klines", fake_fetch_klines)

    result = asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                ema_fast_period=3,
                ema_slow_period=5,
                atr_period=3,
                dmi_period=3,
                swing_lookback=5,
                limit=6,
                history_start_time_ms=-6 * 4 * 60 * 60 * 1000,
                history_end_time_ms=6 * 15 * 60 * 1000 - 1,
            )
        )
    )

    assert result.error is None
    assert ("BTCUSDT", "4h", 6, -86400000, -1) in requested
    assert any(request[:3] == ("BTCUSDT", "1h", 6) for request in requested)
    assert any(request[:3] == ("BTCUSDT", "15m", 6) for request in requested)
    assert result.config.ema_fast_period == 3
    assert result.config.ema_slow_period == 5
    assert result.total_trades == 1
    assert result.final_equity == "1010.00"
    assert result.trades[0]["strategy_type"] == "TREND_PULLBACK"


def test_strategy_backtest_returns_error_when_historical_fetch_fails(monkeypatch):
    from app.data.binance import BinanceDataError
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    async def fake_fetch_klines(
        symbol: str,
        interval: str,
        limit: int,
        settings=None,
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        raise BinanceDataError("HTTP 451")

    monkeypatch.setattr(strategy_backtest, "fetch_klines", fake_fetch_klines)

    result = asyncio.run(run_strategy_backtest(StrategyBacktestConfig(symbols=("BTCUSDT",))))

    assert result.error == "HTTP 451"
    assert result.total_trades == 0
    assert result.trades == []


def test_strategy_backtest_paginates_history_window(monkeypatch):
    from app.data.quality import INTERVAL_MS
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    requests: list[tuple[str, str, int, int | None, int | None]] = []

    async def fake_fetch_klines(
        symbol: str,
        interval: str,
        limit: int,
        settings=None,
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        requests.append((symbol, interval, limit, start_time, end_time))
        if start_time is None or end_time is None or start_time > end_time:
            return []
        return [
            _kline(
                symbol=symbol,
                interval=interval,
                index=start_time // INTERVAL_MS[interval],
                close="100",
            )
        ]

    monkeypatch.setattr(strategy_backtest, "fetch_klines", fake_fetch_klines)

    result = asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                history_period="3m",
                history_end_time_ms=90 * 24 * 60 * 60 * 1000,
                limit=1000,
            )
        )
    )

    assert result.error is None
    first_15m = next(request for request in requests if request[1] == "15m")
    assert first_15m == ("BTCUSDT", "15m", 1000, 0, 899999999)
    assert len([request for request in requests if request[1] == "15m"]) > 1
