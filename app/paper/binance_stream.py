import json
import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.data.quality import Kline


@dataclass(frozen=True)
class TickerPrice:
    symbol: str
    price: Decimal
    event_time_ms: int


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


def parse_binance_ws_ticker_price(message: dict[str, Any]) -> TickerPrice | None:
    if "data" in message and isinstance(message["data"], dict):
        message = message["data"]
    if message.get("e") != "24hrTicker":
        return None
    symbol = str(message.get("s") or "")
    raw_price = message.get("c")
    if not symbol or raw_price is None:
        return None
    return TickerPrice(
        symbol=symbol,
        price=Decimal(str(raw_price)),
        event_time_ms=int(message.get("E") or 0),
    )


def build_binance_kline_stream_url(base_url: str, symbols: list[str], interval: str) -> str:
    streams = "/".join(f"{symbol.lower()}@kline_{interval}" for symbol in symbols)
    return f"{_binance_market_stream_base_url(base_url)}/stream?streams={streams}"


def build_binance_multi_interval_stream_url(base_url: str, symbols: list[str], intervals: list[str]) -> str:
    streams = "/".join(
        f"{symbol.lower()}@kline_{interval}"
        for symbol in symbols
        for interval in intervals
    )
    return f"{_binance_market_stream_base_url(base_url)}/stream?streams={streams}"


def build_binance_ticker_stream_url(base_url: str, symbols: list[str]) -> str:
    streams = "/".join(f"{symbol.lower()}@ticker" for symbol in symbols)
    return f"{_binance_market_stream_base_url(base_url)}/stream?streams={streams}"


async def iter_binance_ws_klines(raw_messages: AsyncIterable[str | dict[str, Any]]) -> AsyncIterator[Kline]:
    async for raw_message in raw_messages:
        message = json.loads(raw_message) if isinstance(raw_message, str) else raw_message
        kline = parse_binance_ws_kline(message)
        if kline is not None:
            yield kline


async def iter_binance_ws_ticker_prices(
    raw_messages: AsyncIterable[str | dict[str, Any]],
) -> AsyncIterator[TickerPrice]:
    async for raw_message in raw_messages:
        message = json.loads(raw_message) if isinstance(raw_message, str) else raw_message
        price = parse_binance_ws_ticker_price(message)
        if price is not None:
            yield price


async def iter_binance_websocket_klines(
    base_url: str,
    symbols: list[str],
    interval: str,
    connect: Callable[[str], Any] | None = None,
    reconnect: bool = False,
    reconnect_initial_delay: float = 1.0,
    reconnect_max_delay: float = 60.0,
) -> AsyncIterator[Kline]:
    url = build_binance_kline_stream_url(base_url=base_url, symbols=symbols, interval=interval)
    async for kline in _iter_reconnecting_websocket_klines(
        url=url,
        connect=connect,
        reconnect=reconnect,
        reconnect_initial_delay=reconnect_initial_delay,
        reconnect_max_delay=reconnect_max_delay,
    ):
        yield kline


async def iter_binance_multi_interval_websocket_klines(
    base_url: str,
    symbols: list[str],
    intervals: list[str],
    connect: Callable[[str], Any] | None = None,
    reconnect: bool = False,
    reconnect_initial_delay: float = 1.0,
    reconnect_max_delay: float = 60.0,
) -> AsyncIterator[Kline]:
    url = build_binance_multi_interval_stream_url(
        base_url=base_url,
        symbols=symbols,
        intervals=intervals,
    )
    async for kline in _iter_reconnecting_websocket_klines(
        url=url,
        connect=connect,
        reconnect=reconnect,
        reconnect_initial_delay=reconnect_initial_delay,
        reconnect_max_delay=reconnect_max_delay,
    ):
        yield kline


async def iter_binance_websocket_ticker_prices(
    base_url: str,
    symbols: list[str],
    connect: Callable[[str], Any] | None = None,
    reconnect: bool = False,
    reconnect_initial_delay: float = 1.0,
    reconnect_max_delay: float = 60.0,
) -> AsyncIterator[TickerPrice]:
    url = build_binance_ticker_stream_url(base_url=base_url, symbols=symbols)
    async for price in _iter_reconnecting_websocket_ticker_prices(
        url=url,
        connect=connect,
        reconnect=reconnect,
        reconnect_initial_delay=reconnect_initial_delay,
        reconnect_max_delay=reconnect_max_delay,
    ):
        yield price


async def _iter_reconnecting_websocket_klines(
    url: str,
    connect: Callable[[str], Any] | None,
    reconnect: bool,
    reconnect_initial_delay: float,
    reconnect_max_delay: float,
) -> AsyncIterator[Kline]:
    connector = connect or _default_websocket_connect
    delay = reconnect_initial_delay
    while True:
        try:
            async with connector(url) as websocket:
                async for kline in iter_binance_ws_klines(websocket):
                    delay = reconnect_initial_delay
                    yield kline
            return
        except Exception as exc:
            if not reconnect:
                raise
            print(f"Binance WebSocket reconnecting after error: {exc}")
            if delay > 0:
                await asyncio.sleep(delay)
            delay = min(max(delay * 2, reconnect_initial_delay), reconnect_max_delay)


async def _iter_reconnecting_websocket_ticker_prices(
    url: str,
    connect: Callable[[str], Any] | None,
    reconnect: bool,
    reconnect_initial_delay: float,
    reconnect_max_delay: float,
) -> AsyncIterator[TickerPrice]:
    connector = connect or _default_websocket_connect
    delay = reconnect_initial_delay
    while True:
        try:
            async with connector(url) as websocket:
                async for price in iter_binance_ws_ticker_prices(websocket):
                    delay = reconnect_initial_delay
                    yield price
            return
        except Exception as exc:
            if not reconnect:
                raise
            print(f"Binance ticker WebSocket reconnecting after error: {exc}")
            if delay > 0:
                await asyncio.sleep(delay)
            delay = min(max(delay * 2, reconnect_initial_delay), reconnect_max_delay)


def _binance_market_stream_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.netloc == "fstream.binance.com" and parsed.path in ("", "/"):
        return urlunsplit((parsed.scheme, parsed.netloc, "/market", "", ""))
    return normalized


def _default_websocket_connect(url: str) -> Any:
    import websockets

    return websockets.connect(url, ping_interval=180, ping_timeout=600, close_timeout=10)
