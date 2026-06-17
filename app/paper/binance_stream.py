import json
from collections.abc import AsyncIterable, AsyncIterator, Callable
from decimal import Decimal
from typing import Any

from app.data.quality import Kline


def parse_binance_ws_kline(message: dict[str, Any]) -> Kline | None:
    if "data" in message and isinstance(message["data"], dict):
        message = message["data"]
    payload = message.get("k")
    if not isinstance(payload, dict) or payload.get("x") is not True:
        return None
    symbol = str(payload["s"])
    interval = str(payload["i"])
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=int(payload["t"]),
        close_time=int(payload["T"]),
        open=Decimal(str(payload["o"])),
        high=Decimal(str(payload["h"])),
        low=Decimal(str(payload["l"])),
        close=Decimal(str(payload["c"])),
        volume=Decimal(str(payload["v"])),
        is_closed=True,
    )


def build_binance_kline_stream_url(base_url: str, symbols: list[str], interval: str) -> str:
    streams = "/".join(f"{symbol.lower()}@kline_{interval}" for symbol in symbols)
    return f"{base_url.rstrip('/')}/stream?streams={streams}"


async def iter_binance_ws_klines(raw_messages: AsyncIterable[str | dict[str, Any]]) -> AsyncIterator[Kline]:
    async for raw_message in raw_messages:
        message = json.loads(raw_message) if isinstance(raw_message, str) else raw_message
        kline = parse_binance_ws_kline(message)
        if kline is not None:
            yield kline


async def iter_binance_websocket_klines(
    base_url: str,
    symbols: list[str],
    interval: str,
    connect: Callable[[str], Any] | None = None,
) -> AsyncIterator[Kline]:
    url = build_binance_kline_stream_url(base_url=base_url, symbols=symbols, interval=interval)
    connector = connect or _default_websocket_connect
    async with connector(url) as websocket:
        async for kline in iter_binance_ws_klines(websocket):
            yield kline


def _default_websocket_connect(url: str) -> Any:
    import websockets

    return websockets.connect(url)
