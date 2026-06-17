from decimal import Decimal
import json


def test_parses_closed_binance_websocket_kline_message():
    from app.paper.binance_stream import parse_binance_ws_kline

    message = {
        "e": "kline",
        "E": 1710000000000,
        "s": "BTCUSDT",
        "k": {
            "t": 0,
            "T": 899_999,
            "s": "BTCUSDT",
            "i": "15m",
            "o": "100.00",
            "h": "110.00",
            "l": "95.00",
            "c": "105.00",
            "v": "12.500",
            "x": True,
        },
    }

    kline = parse_binance_ws_kline(message)

    assert kline is not None
    assert kline.symbol == "BTCUSDT"
    assert kline.interval == "15m"
    assert kline.open_time == 0
    assert kline.close_time == 899_999
    assert kline.open == Decimal("100.00")
    assert kline.close == Decimal("105.00")
    assert kline.is_closed is True


def test_ignores_unclosed_binance_websocket_kline_message():
    from app.paper.binance_stream import parse_binance_ws_kline

    message = {
        "e": "kline",
        "s": "ETHUSDT",
        "k": {
            "t": 0,
            "T": 899_999,
            "s": "ETHUSDT",
            "i": "15m",
            "o": "100.00",
            "h": "110.00",
            "l": "95.00",
            "c": "105.00",
            "v": "12.500",
            "x": False,
        },
    }

    assert parse_binance_ws_kline(message) is None


def test_builds_binance_combined_kline_stream_url():
    from app.paper.binance_stream import build_binance_kline_stream_url

    url = build_binance_kline_stream_url(
        base_url="wss://fstream.binance.com",
        symbols=["BTCUSDT", "ETHUSDT"],
        interval="15m",
    )

    assert url == "wss://fstream.binance.com/stream?streams=btcusdt@kline_15m/ethusdt@kline_15m"


def test_iterates_closed_klines_from_raw_websocket_messages():
    import asyncio

    from app.paper.binance_stream import iter_binance_ws_klines

    async def raw_messages():
        for closed in [False, True]:
            yield json.dumps(
                {
                    "stream": "btcusdt@kline_15m",
                    "data": {
                        "e": "kline",
                        "s": "BTCUSDT",
                        "k": {
                            "t": 0 if not closed else 900_000,
                            "T": 899_999 if not closed else 1_799_999,
                            "s": "BTCUSDT",
                            "i": "15m",
                            "o": "100.00",
                            "h": "110.00",
                            "l": "95.00",
                            "c": "105.00",
                            "v": "12.500",
                            "x": closed,
                        },
                    },
                }
            )

    async def collect():
        return [kline async for kline in iter_binance_ws_klines(raw_messages())]

    klines = asyncio.run(collect())

    assert len(klines) == 1
    assert klines[0].open_time == 900_000


def test_iterates_binance_websocket_klines_with_injected_connector():
    import asyncio

    from app.paper.binance_stream import iter_binance_websocket_klines

    class FakeWebSocket:
        def __init__(self, messages):
            self.messages = messages

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.messages:
                raise StopAsyncIteration
            return self.messages.pop(0)

    captured_urls = []

    def fake_connect(url):
        captured_urls.append(url)
        return FakeWebSocket(
            [
                json.dumps(
                    {
                        "stream": "btcusdt@kline_15m",
                        "data": {
                            "e": "kline",
                            "s": "BTCUSDT",
                            "k": {
                                "t": 0,
                                "T": 899_999,
                                "s": "BTCUSDT",
                                "i": "15m",
                                "o": "100.00",
                                "h": "110.00",
                                "l": "95.00",
                                "c": "105.00",
                                "v": "12.500",
                                "x": True,
                            },
                        },
                    }
                )
            ]
        )

    async def collect():
        return [
            kline
            async for kline in iter_binance_websocket_klines(
                base_url="wss://fstream.binance.com",
                symbols=["BTCUSDT"],
                interval="15m",
                connect=fake_connect,
            )
        ]

    klines = asyncio.run(collect())

    assert captured_urls == ["wss://fstream.binance.com/stream?streams=btcusdt@kline_15m"]
    assert len(klines) == 1
    assert klines[0].symbol == "BTCUSDT"
