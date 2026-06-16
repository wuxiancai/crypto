from decimal import Decimal
from typing import Any

import httpx

from app.config.settings import Settings
from app.data.quality import Kline


class BinanceDataError(RuntimeError):
    pass


def parse_binance_kline(symbol: str, interval: str, payload: list[Any]) -> Kline:
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=int(payload[0]),
        open=Decimal(str(payload[1])),
        high=Decimal(str(payload[2])),
        low=Decimal(str(payload[3])),
        close=Decimal(str(payload[4])),
        volume=Decimal(str(payload[5])),
        close_time=int(payload[6]),
        is_closed=True,
    )


async def fetch_klines(
    symbol: str,
    interval: str,
    limit: int = 500,
    settings: Settings | None = None,
) -> list[Kline]:
    config = settings or Settings()
    async with httpx.AsyncClient(base_url=config.binance_base_url, timeout=20.0) as client:
        response = await client.get(
            "/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 451:
                raise BinanceDataError(
                    "Binance futures data endpoint returned HTTP 451. "
                    "The current network or region may be restricted. "
                    "Set BINANCE_BASE_URL to an accessible futures endpoint for validation."
                ) from exc
            raise BinanceDataError(f"Binance kline request failed: {exc.response.status_code}") from exc
        payload = response.json()
    return [parse_binance_kline(symbol, interval, item) for item in payload]
