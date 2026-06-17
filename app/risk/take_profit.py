from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TakeProfitLevel:
    name: str
    price: Decimal
    close_pct: Decimal


@dataclass(frozen=True)
class TakeProfitPlan:
    levels: tuple[TakeProfitLevel, ...]
    move_stop_to_break_even_after: str


def build_reversal_take_profit_plan(
    side: str,
    entry_price: Decimal,
    stop_loss: Decimal,
    previous_high: Decimal,
    previous_low: Decimal,
    ema200_4h: Decimal,
) -> TakeProfitPlan:
    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        raise ValueError("risk must be positive")
    if side == "LONG":
        levels = (
            TakeProfitLevel("TP1", entry_price + risk, Decimal("0.30")),
            TakeProfitLevel("TP2", previous_high, Decimal("0.30")),
            TakeProfitLevel(
                "TP3",
                _long_tp3(entry_price, risk, previous_high, ema200_4h),
                Decimal("0.40"),
            ),
        )
    elif side == "SHORT":
        levels = (
            TakeProfitLevel("TP1", entry_price - risk, Decimal("0.30")),
            TakeProfitLevel("TP2", previous_low, Decimal("0.30")),
            TakeProfitLevel(
                "TP3",
                _short_tp3(entry_price, risk, previous_low, ema200_4h),
                Decimal("0.40"),
            ),
        )
    else:
        raise ValueError(f"unsupported side: {side}")
    return TakeProfitPlan(levels=levels, move_stop_to_break_even_after="TP1")


def _long_tp3(
    entry_price: Decimal,
    risk: Decimal,
    previous_high: Decimal,
    ema200_4h: Decimal,
) -> Decimal:
    if ema200_4h > entry_price:
        return ema200_4h
    return max(previous_high, entry_price + risk * Decimal("3"))


def _short_tp3(
    entry_price: Decimal,
    risk: Decimal,
    previous_low: Decimal,
    ema200_4h: Decimal,
) -> Decimal:
    if ema200_4h < entry_price:
        return ema200_4h
    return min(previous_low, entry_price - risk * Decimal("3"))
