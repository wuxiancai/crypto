from dataclasses import dataclass
from decimal import Decimal, getcontext

getcontext().prec = 28


@dataclass(frozen=True)
class BollingerBand:
    upper: Decimal
    middle: Decimal
    lower: Decimal
    width_pct: Decimal


@dataclass(frozen=True)
class DirectionalMovement:
    adx: Decimal
    di_plus: Decimal
    di_minus: Decimal


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


def directional_movement_index(
    highs: list[Decimal],
    lows: list[Decimal],
    closes: list[Decimal],
    period: int,
) -> list[DirectionalMovement | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    _ensure_same_length(highs, lows, closes)
    if not highs:
        return []

    ranges = true_ranges(highs, lows, closes)
    plus_dm: list[Decimal] = [Decimal("0")]
    minus_dm: list[Decimal] = [Decimal("0")]
    for index in range(1, len(highs)):
        up_move = highs[index] - highs[index - 1]
        down_move = lows[index - 1] - lows[index]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else Decimal("0"))
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else Decimal("0"))

    result: list[DirectionalMovement | None] = []
    dx_values: list[Decimal | None] = []
    for index in range(len(highs)):
        if index + 1 < period:
            result.append(None)
            dx_values.append(None)
            continue
        tr_sum = sum(ranges[index + 1 - period : index + 1])
        plus_sum = sum(plus_dm[index + 1 - period : index + 1])
        minus_sum = sum(minus_dm[index + 1 - period : index + 1])
        if tr_sum == 0:
            di_plus = Decimal("0")
            di_minus = Decimal("0")
        else:
            di_plus = Decimal("100") * plus_sum / tr_sum
            di_minus = Decimal("100") * minus_sum / tr_sum
        denominator = di_plus + di_minus
        dx = Decimal("0") if denominator == 0 else Decimal("100") * abs(di_plus - di_minus) / denominator
        dx_values.append(dx)
        valid_dx = [value for value in dx_values[index + 1 - period : index + 1] if value is not None]
        adx = sum(valid_dx) / Decimal(len(valid_dx)) if valid_dx else Decimal("0")
        result.append(DirectionalMovement(adx=adx, di_plus=di_plus, di_minus=di_minus))
    return result


def _ensure_same_length(*series: list[Decimal]) -> None:
    lengths = {len(item) for item in series}
    if len(lengths) != 1:
        raise ValueError("all series must have the same length")
