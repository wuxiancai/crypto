from dataclasses import dataclass, replace
from decimal import Decimal


@dataclass(frozen=True)
class ExecutionState:
    plan_id: str
    quantity: Decimal
    filled_quantity: Decimal
    order_status: str
    position_status: str
    stop_order_status: str
    take_profit_status: str
    risk_status: str
    allow_new_entries: bool
    required_action: str | None = None

    @classmethod
    def new(cls, plan_id: str, quantity: Decimal) -> "ExecutionState":
        return cls(
            plan_id=plan_id,
            quantity=quantity,
            filled_quantity=Decimal("0"),
            order_status="PLANNED",
            position_status="FLAT",
            stop_order_status="NOT_REQUIRED",
            take_profit_status="NOT_SUBMITTED",
            risk_status="WAITING_ENTRY",
            allow_new_entries=True,
        )


def apply_execution_event(
    state: ExecutionState,
    event: str,
    fill_quantity: Decimal = Decimal("0"),
) -> ExecutionState:
    if event == "ENTRY_SUBMITTED":
        return replace(state, order_status="SUBMITTED", risk_status="ENTRY_PENDING")
    if event == "ENTRY_PARTIALLY_FILLED":
        return _apply_entry_fill(state, fill_quantity, is_complete=False)
    if event == "ENTRY_FILLED":
        return _apply_entry_fill(state, fill_quantity, is_complete=True)
    if event == "STOP_SUBMITTED":
        return replace(state, stop_order_status="SUBMITTED", risk_status="STOP_PENDING")
    if event == "STOP_CONFIRMED":
        return replace(state, stop_order_status="CONFIRMED", risk_status="PROTECTED")
    if event == "STOP_FAILED":
        return replace(
            state,
            stop_order_status="FAILED",
            risk_status="CRITICAL",
            allow_new_entries=False,
            required_action="RETRY_STOP_OR_MARKET_CLOSE",
        )
    if event == "TAKE_PROFIT_SUBMITTED":
        return replace(state, take_profit_status="SUBMITTED")
    if event == "EXIT_FILLED":
        return replace(
            state,
            order_status="CLOSED",
            position_status="CLOSED",
            filled_quantity=Decimal("0"),
            risk_status="CLOSED",
            allow_new_entries=True,
            required_action=None,
        )
    raise ValueError(f"unsupported execution event: {event}")


def _apply_entry_fill(
    state: ExecutionState,
    fill_quantity: Decimal,
    is_complete: bool,
) -> ExecutionState:
    filled_quantity = state.filled_quantity + fill_quantity
    if is_complete:
        return replace(
            state,
            filled_quantity=filled_quantity,
            order_status="FILLED",
            position_status="OPEN",
            stop_order_status="PENDING_SUBMISSION",
            risk_status="UNPROTECTED",
        )
    return replace(
        state,
        filled_quantity=filled_quantity,
        order_status="PARTIALLY_FILLED",
        position_status="OPEN",
        stop_order_status="PENDING_SUBMISSION",
        risk_status="UNPROTECTED",
    )
