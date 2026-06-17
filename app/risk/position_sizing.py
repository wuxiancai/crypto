from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PositionSize:
    quantity: Decimal
    risk_amount: Decimal
    notional: Decimal
    is_valid: bool


def calculate_main_position_size(
    account_equity: Decimal,
    risk_per_trade_pct: Decimal,
    entry_price: Decimal,
    stop_loss: Decimal,
    quantity_step: Decimal,
    min_qty: Decimal,
    min_notional: Decimal,
) -> PositionSize:
    risk_amount = account_equity * risk_per_trade_pct
    raw_quantity = risk_amount / abs(entry_price - stop_loss)
    quantity = _floor_to_step(raw_quantity, quantity_step)
    return _position_size(quantity, risk_amount, entry_price, min_qty, min_notional)


def calculate_reversal_position_size(
    account_equity: Decimal,
    standard_quantity: Decimal,
    signal_level: str,
    score: Decimal,
    entry_price: Decimal,
    stop_loss: Decimal,
    quantity_step: Decimal,
    min_qty: Decimal,
    min_notional: Decimal,
) -> PositionSize:
    risk_pct = Decimal("0.002") if signal_level == "EARLY" else Decimal("0.003")
    risk_amount = account_equity * risk_pct
    risk_limited_quantity = risk_amount / abs(entry_price - stop_loss)
    score_limited_quantity = standard_quantity * _score_multiplier(score)
    quantity = _floor_to_step(min(risk_limited_quantity, score_limited_quantity), quantity_step)
    actual_risk_amount = quantity * abs(entry_price - stop_loss)
    return _position_size(quantity, actual_risk_amount, entry_price, min_qty, min_notional)


def _score_multiplier(score: Decimal) -> Decimal:
    if score < Decimal("70"):
        return Decimal("0")
    if score < Decimal("75"):
        return Decimal("0.2")
    if score < Decimal("85"):
        return Decimal("0.3")
    return Decimal("0.5")


def _position_size(
    quantity: Decimal,
    risk_amount: Decimal,
    entry_price: Decimal,
    min_qty: Decimal,
    min_notional: Decimal,
) -> PositionSize:
    notional = quantity * entry_price
    return PositionSize(
        quantity=quantity,
        risk_amount=risk_amount,
        notional=notional,
        is_valid=quantity >= min_qty and notional >= min_notional,
    )


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value // step) * step
