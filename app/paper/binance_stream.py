from decimal import Decimal
from typing import Any

from app.data.quality import Kline


def parse_binance_ws_kline(message: dict[str, Any]) -> Kline | None:
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
