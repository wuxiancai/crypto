from dataclasses import dataclass
from decimal import Decimal

from app.risk.take_profit import TakeProfitLevel, TakeProfitPlan


@dataclass(frozen=True)
class OrderPlan:
    symbol: str
    side: str
    strategy_type: str
    signal_id: str
    order_type: str
    entry_price: Decimal
    quantity: Decimal
    stop_loss: Decimal
    take_profit_levels: tuple[TakeProfitLevel, ...]
    leverage: Decimal
    margin_type: str
    position_mode: str
    estimated_liquidation_price: Decimal
    liquidation_buffer_pct: Decimal
    reduce_only: bool
    client_order_id: str
    strategy_version: str
    config_snapshot_id: str
    move_stop_to_break_even_after: str


def build_order_plan(
    symbol: str,
    side: str,
    strategy_type: str,
    signal_id: str,
    order_type: str,
    entry_price: Decimal,
    quantity: Decimal,
    stop_loss: Decimal,
    take_profit_plan: TakeProfitPlan,
    strategy_version: str,
    config_snapshot_id: str,
    estimated_liquidation_price: Decimal,
    liquidation_buffer_pct: Decimal,
    leverage: Decimal = Decimal("10"),
    max_leverage: Decimal = Decimal("10"),
    margin_type: str = "ISOLATED",
    position_mode: str = "ONE_WAY",
    reduce_only: bool = False,
) -> OrderPlan:
    _validate_execution_constraints(leverage, max_leverage, margin_type, position_mode)
    return OrderPlan(
        symbol=symbol,
        side=side,
        strategy_type=strategy_type,
        signal_id=signal_id,
        order_type=order_type,
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit_levels=take_profit_plan.levels,
        leverage=leverage,
        margin_type=margin_type,
        position_mode=position_mode,
        estimated_liquidation_price=estimated_liquidation_price,
        liquidation_buffer_pct=liquidation_buffer_pct,
        reduce_only=reduce_only,
        client_order_id=f"{strategy_type}-{signal_id}-{side}",
        strategy_version=strategy_version,
        config_snapshot_id=config_snapshot_id,
        move_stop_to_break_even_after=take_profit_plan.move_stop_to_break_even_after,
    )


def _validate_execution_constraints(
    leverage: Decimal,
    max_leverage: Decimal,
    margin_type: str,
    position_mode: str,
) -> None:
    if leverage > max_leverage:
        raise ValueError("leverage exceeds max_leverage")
    if margin_type != "ISOLATED":
        raise ValueError("margin_type must be ISOLATED")
    if position_mode != "ONE_WAY":
        raise ValueError("position_mode must be ONE_WAY")
