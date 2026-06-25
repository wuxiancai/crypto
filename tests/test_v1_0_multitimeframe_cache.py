from decimal import Decimal


def _kline(symbol: str, interval: str, open_time: int, close: str):
    from app.data.quality import Kline

    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=open_time,
        close_time=open_time + 899_999,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("10"),
    )


def test_multitimeframe_cache_returns_none_until_required_timeframes_are_present():
    from app.paper.multitimeframe import MultiTimeframeKlineCache

    cache = MultiTimeframeKlineCache(required_intervals=("15m", "1h", "4h"))

    assert cache.update(_kline("BTCUSDT", "15m", 0, "100")) is None
    assert cache.update(_kline("BTCUSDT", "1h", 0, "101")) is None


def test_multitimeframe_cache_returns_latest_closed_frame_for_symbol():
    from app.paper.multitimeframe import MultiTimeframeKlineCache

    cache = MultiTimeframeKlineCache(required_intervals=("15m", "1h", "4h"))
    cache.update(_kline("BTCUSDT", "15m", 0, "100"))
    cache.update(_kline("BTCUSDT", "1h", 0, "101"))

    frame = cache.update(_kline("BTCUSDT", "4h", 0, "102"))

    assert frame is not None
    assert frame.symbol == "BTCUSDT"
    assert frame.latest("15m").close == Decimal("100")
    assert frame.latest("1h").close == Decimal("101")
    assert frame.latest("4h").close == Decimal("102")


def test_multitimeframe_cache_deduplicates_by_open_time_and_sorts_before_trimming():
    from app.paper.multitimeframe import MultiTimeframeKlineCache

    cache = MultiTimeframeKlineCache(required_intervals=("15m",), max_klines_per_interval=2)
    cache.update(_kline("BTCUSDT", "15m", 2, "102"))
    cache.update(_kline("BTCUSDT", "15m", 1, "101"))
    frame = cache.update(_kline("BTCUSDT", "15m", 2, "202"))

    assert frame is not None
    assert [kline.open_time for kline in frame.history("15m")] == [1, 2]
    assert [kline.close for kline in frame.history("15m")] == [Decimal("101"), Decimal("202")]


def test_multitimeframe_cache_keeps_symbols_isolated_and_bounded():
    from app.paper.multitimeframe import MultiTimeframeKlineCache

    cache = MultiTimeframeKlineCache(required_intervals=("15m", "1h"), max_klines_per_interval=2)
    cache.update(_kline("BTCUSDT", "15m", 0, "100"))
    cache.update(_kline("BTCUSDT", "15m", 1, "101"))
    cache.update(_kline("BTCUSDT", "15m", 2, "102"))
    cache.update(_kline("ETHUSDT", "1h", 0, "200"))

    frame = cache.update(_kline("BTCUSDT", "1h", 0, "103"))

    assert frame is not None
    assert [kline.close for kline in frame.history("15m")] == [Decimal("101"), Decimal("102")]
    assert frame.latest("1h").close == Decimal("103")
