from dataclasses import dataclass
from decimal import Decimal, getcontext

getcontext().prec = 28


@dataclass(frozen=True)
class BollingerBand:
    upper: Decimal
    middle: Decimal
    lower: Decimal
    width_pct: Decimal


def ema(values: list[Decimal], period: int) -> list[Decimal | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not values:
        return []

    multiplier = Decimal(2) / Decimal(period + 1)
    result: list[Decimal | None] = []
    current: Decimal | None = None
    for value in values:
        current = value if current is None else (value - current) * multiplier + current
        result.append(current)
    return result


def true_ranges(highs: list[Decimal], lows: list[Decimal], closes: list[Decimal]) -> list[Decimal]:
    _ensure_same_length(highs, lows, closes)
    ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for high, low, close in zip(highs, lows, closes, strict=True):
        if previous_close is None:
            ranges.append(high - low)
        else:
            ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = close
    return ranges


def atr(highs: list[Decimal], lows: list[Decimal], closes: list[Decimal], period: int) -> list[Decimal | None]:
    ranges = true_ranges(highs, lows, closes)
    result: list[Decimal | None] = []
    for index in range(len(ranges)):
        if index + 1 < period:
            result.append(None)
            continue
        window = ranges[index + 1 - period : index + 1]
        result.append(sum(window) / Decimal(period))
    return result


def bollinger_bands(values: list[Decimal], period: int, stddev: Decimal) -> list[BollingerBand | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    result: list[BollingerBand | None] = []
    for index in range(len(values)):
        if index + 1 < period:
            result.append(None)
            continue
        window = values[index + 1 - period : index + 1]
        middle = sum(window) / Decimal(period)
        variance = sum((value - middle) ** 2 for value in window) / Decimal(period)
        deviation = Decimal(str(float(variance) ** 0.5))
        upper = middle + stddev * deviation
        lower = middle - stddev * deviation
        width_pct = (upper - lower) / middle if middle != 0 else Decimal("0")
        result.append(BollingerBand(upper=upper, middle=middle, lower=lower, width_pct=width_pct))
    return result


def _ensure_same_length(*series: list[Decimal]) -> None:
    lengths = {len(item) for item in series}
    if len(lengths) != 1:
        raise ValueError("all series must have the same length")

