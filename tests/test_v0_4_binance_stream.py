from decimal import Decimal


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
