from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


INTERVAL_MS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
}


class Kline(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    interval: str
    open_time: int
    close_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_closed: bool = True

    @field_validator("interval")
    @classmethod
    def known_interval(cls, value: str) -> str:
        if value not in INTERVAL_MS:
            raise ValueError(f"unsupported interval: {value}")
        return value


def validate_kline_sequence(rows: list[Kline]) -> list[str]:
    errors: list[str] = []
    if not rows:
        return errors

    sorted_rows = sorted(rows, key=lambda row: row.open_time)
    for index, row in enumerate(sorted_rows):
        prefix = f"{row.symbol} {row.interval} {row.open_time}"
        if not row.is_closed:
            errors.append(f"{prefix}: kline is not closed")
        if row.high < max(row.open, row.close, row.low):
            errors.append(f"{prefix}: high violates OHLC rules")
        if row.low > min(row.open, row.close, row.high):
            errors.append(f"{prefix}: low violates OHLC rules")
        if row.volume < 0:
            errors.append(f"{prefix}: volume is negative")
        expected_close = row.open_time + INTERVAL_MS[row.interval] - 1
        if row.close_time != expected_close:
            errors.append(f"{prefix}: close_time does not match interval")
        if index == 0:
            continue
        previous = sorted_rows[index - 1]
        expected_open = previous.open_time + INTERVAL_MS[row.interval]
        if row.open_time != expected_open:
            errors.append(f"{prefix}: time series is not continuous")
    return errors

