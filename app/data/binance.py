from decimal import Decimal
from typing import Any
import asyncio
import time

import httpx

from app.config.settings import Settings
from app.data.quality import Kline


class BinanceDataError(RuntimeError):
    pass


RETRYABLE_STATUS_CODES = {408, 429, 503}


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
    start_time: int | None = None,
    end_time: int | None = None,
    max_attempts: int = 3,
    retry_initial_delay: float = 0.2,
    now_ms: int | None = None,
) -> list[Kline]:
    config = settings or Settings()
    params: dict[str, int | str] = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_time is not None:
        params["startTime"] = start_time
    if end_time is not None:
        params["endTime"] = end_time
    attempt = 0
    delay = retry_initial_delay
    while True:
        attempt += 1
        try:
            async with httpx.AsyncClient(base_url=config.binance_base_url, timeout=20.0) as client:
                response = await client.get(
                    "/fapi/v1/klines",
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
                break
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 451:
                raise BinanceDataError(
                    "Binance futures data endpoint returned HTTP 451. "
                    "The current network or region may be restricted. "
                    "Set BINANCE_BASE_URL to an accessible futures endpoint for validation."
                ) from exc
            if exc.response.status_code not in RETRYABLE_STATUS_CODES or attempt >= max_attempts:
                raise BinanceDataError(f"Binance kline request failed: {exc.response.status_code}") from exc
        except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
            if attempt >= max_attempts:
                raise BinanceDataError(f"Binance kline request failed after retries: {exc}") from exc
        await asyncio.sleep(delay)
        delay *= 2
    effective_now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    return [
        row
        for row in (parse_binance_kline(symbol, interval, item) for item in payload)
        if row.close_time <= effective_now_ms
    ]
