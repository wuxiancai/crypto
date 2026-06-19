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
                history_cache_dir=None,
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
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


def test_strategy_backtest_defaults_to_perpetual_contract_costs():
    from app.paper.strategy_backtest import StrategyBacktestConfig

    config = StrategyBacktestConfig()

    assert config.maker_fee_rate == Decimal("0.0002")
    assert config.taker_fee_rate == Decimal("0.0005")
    assert config.leverage == Decimal("10")
    assert config.funding_rate == Decimal("0")
    assert config.funding_interval_ms == 8 * 60 * 60 * 1000
    assert config.trend_pullback_take_profit_mode == "TRAILING"


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
                history_cache_dir=None,
                limit=1000,
            )
        )
    )

    assert result.error is None
    first_15m = next(request for request in requests if request[1] == "15m")
    assert first_15m == ("BTCUSDT", "15m", 1000, 0, 899999999)
    assert len([request for request in requests if request[1] == "15m"]) > 1


def test_strategy_backtest_reuses_cached_klines_and_fetches_only_missing_tail(monkeypatch, tmp_path):
    from app.data.quality import INTERVAL_MS
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    requests: list[tuple[int | None, int | None]] = []

    async def fake_fetch_klines(
        symbol: str,
        interval: str,
        limit: int,
        settings=None,
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        requests.append((start_time, end_time))
        if start_time is None or end_time is None or start_time > end_time:
            return []
        interval_ms = INTERVAL_MS[interval]
        start_index = start_time // interval_ms
        end_index = end_time // interval_ms
        return [_kline(symbol, interval, index, "100") for index in range(start_index, end_index + 1)]

    monkeypatch.setattr(strategy_backtest, "fetch_klines", fake_fetch_klines)
    base = StrategyBacktestConfig(
        symbols=("BTCUSDT",),
        history_start_time_ms=0,
        history_end_time_ms=4 * INTERVAL_MS["15m"] - 1,
        history_cache_dir=tmp_path / "backtest-klines",
        limit=10,
    )

    asyncio.run(run_strategy_backtest(base))
    first_run_requests = len(requests)
    assert first_run_requests > 0

    asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                ema_fast_period=30,
                ema_slow_period=120,
                history_start_time_ms=0,
                history_end_time_ms=2 * INTERVAL_MS["15m"] - 1,
                history_cache_dir=tmp_path / "backtest-klines",
                limit=10,
            )
        )
    )
    assert len(requests) == first_run_requests

    asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                history_start_time_ms=0,
                history_end_time_ms=5 * INTERVAL_MS["15m"] - 1,
                history_cache_dir=tmp_path / "backtest-klines",
                limit=10,
            )
        )
    )
    assert len(requests) == first_run_requests + 2
    assert requests[-1] == (4 * INTERVAL_MS["15m"], 5 * INTERVAL_MS["15m"] - 1)
