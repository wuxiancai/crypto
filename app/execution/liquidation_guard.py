from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LiquidationGuardResult:
    is_safe: bool
    reasons: tuple[str, ...]


def evaluate_liquidation_guard(
    side: str,
    entry_price: Decimal,
    stop_loss: Decimal,
    estimated_liquidation_price: Decimal,
    liquidation_buffer_pct: Decimal,
) -> LiquidationGuardResult:
    if side == "LONG":
        return _evaluate_long(
            entry_price,
            stop_loss,
            estimated_liquidation_price,
            liquidation_buffer_pct,
        )
    if side == "SHORT":
        return _evaluate_short(
            entry_price,
            stop_loss,
            estimated_liquidation_price,
            liquidation_buffer_pct,
        )
    raise ValueError(f"unsupported side: {side}")


def _evaluate_long(
    entry_price: Decimal,
    stop_loss: Decimal,
    estimated_liquidation_price: Decimal,
    liquidation_buffer_pct: Decimal,
) -> LiquidationGuardResult:
    if not estimated_liquidation_price < stop_loss < entry_price:
        return LiquidationGuardResult(is_safe=False, reasons=("invalid_price_order",))
    buffer_pct = (stop_loss - estimated_liquidation_price) / entry_price
    if buffer_pct < liquidation_buffer_pct:
        return LiquidationGuardResult(is_safe=False, reasons=("stop_too_close_to_liquidation",))
    return LiquidationGuardResult(is_safe=True, reasons=())


def _evaluate_short(
    entry_price: Decimal,
    stop_loss: Decimal,
    estimated_liquidation_price: Decimal,
    liquidation_buffer_pct: Decimal,
) -> LiquidationGuardResult:
    if not entry_price < stop_loss < estimated_liquidation_price:
        return LiquidationGuardResult(is_safe=False, reasons=("invalid_price_order",))
    buffer_pct = (estimated_liquidation_price - stop_loss) / entry_price
    if buffer_pct < liquidation_buffer_pct:
        return LiquidationGuardResult(is_safe=False, reasons=("stop_too_close_to_liquidation",))
    return LiquidationGuardResult(is_safe=True, reasons=())
