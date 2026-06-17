from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal


@dataclass(frozen=True)
class StopOrderSnapshot:
    symbol: str
    side: str
    quantity: Decimal
    stop_price: Decimal
    reduce_only: bool
    status: str


@dataclass(frozen=True)
class StopOrderGuardResult:
    is_protected: bool
    action: str
    reasons: tuple[str, ...]


def evaluate_stop_order_guard(
    position: PositionSnapshot,
    stop_orders: Iterable[StopOrderSnapshot],
) -> StopOrderGuardResult:
    has_valid_stop = any(
        _is_valid_stop_order(position, stop_order)
        for stop_order in stop_orders
    )
    if has_valid_stop:
        return StopOrderGuardResult(is_protected=True, action="NONE", reasons=())
    return StopOrderGuardResult(
        is_protected=False,
        action="REPAIR_STOP_ORDER",
        reasons=("missing_valid_stop_order",),
    )


def _is_valid_stop_order(position: PositionSnapshot, stop_order: StopOrderSnapshot) -> bool:
    return (
        stop_order.symbol == position.symbol
        and stop_order.side == _exit_side(position.side)
        and stop_order.quantity >= position.quantity
        and stop_order.reduce_only is True
        and stop_order.status == "NEW"
        and _is_trigger_price_valid(position, stop_order.stop_price)
    )


def _exit_side(position_side: str) -> str:
    if position_side == "LONG":
        return "SELL"
    if position_side == "SHORT":
        return "BUY"
    raise ValueError(f"unsupported position side: {position_side}")


def _is_trigger_price_valid(position: PositionSnapshot, stop_price: Decimal) -> bool:
    if position.side == "LONG":
        return stop_price < position.entry_price
    if position.side == "SHORT":
        return stop_price > position.entry_price
    raise ValueError(f"unsupported position side: {position.side}")
