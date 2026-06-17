from decimal import Decimal


def test_execution_state_machine_tracks_entry_submission_and_fills():
    from app.execution.state_machine import ExecutionState, apply_execution_event

    state = ExecutionState.new(plan_id="plan-001", quantity=Decimal("1.0"))

    submitted = apply_execution_event(state, "ENTRY_SUBMITTED")
    partial = apply_execution_event(submitted, "ENTRY_PARTIALLY_FILLED", fill_quantity=Decimal("0.4"))
    filled = apply_execution_event(partial, "ENTRY_FILLED", fill_quantity=Decimal("0.6"))

    assert filled.order_status == "FILLED"
    assert filled.position_status == "OPEN"
    assert filled.filled_quantity == Decimal("1.0")
    assert filled.stop_order_status == "PENDING_SUBMISSION"
    assert filled.allow_new_entries is True


def test_execution_state_machine_confirms_stop_then_take_profit_submission():
    from app.execution.state_machine import ExecutionState, apply_execution_event

    state = ExecutionState.new(plan_id="plan-001", quantity=Decimal("1.0"))
    state = apply_execution_event(state, "ENTRY_SUBMITTED")
    state = apply_execution_event(state, "ENTRY_FILLED", fill_quantity=Decimal("1.0"))
    state = apply_execution_event(state, "STOP_SUBMITTED")
    state = apply_execution_event(state, "STOP_CONFIRMED")
    state = apply_execution_event(state, "TAKE_PROFIT_SUBMITTED")

    assert state.stop_order_status == "CONFIRMED"
    assert state.take_profit_status == "SUBMITTED"
    assert state.risk_status == "PROTECTED"


def test_execution_state_machine_escalates_when_stop_submission_fails_after_fill():
    from app.execution.state_machine import ExecutionState, apply_execution_event

    state = ExecutionState.new(plan_id="plan-001", quantity=Decimal("1.0"))
    state = apply_execution_event(state, "ENTRY_SUBMITTED")
    state = apply_execution_event(state, "ENTRY_FILLED", fill_quantity=Decimal("1.0"))
    state = apply_execution_event(state, "STOP_FAILED")

    assert state.stop_order_status == "FAILED"
    assert state.risk_status == "CRITICAL"
    assert state.allow_new_entries is False
    assert state.required_action == "RETRY_STOP_OR_MARKET_CLOSE"


def test_execution_state_machine_closes_position_after_exit_fill():
    from app.execution.state_machine import ExecutionState, apply_execution_event

    state = ExecutionState.new(plan_id="plan-001", quantity=Decimal("1.0"))
    state = apply_execution_event(state, "ENTRY_SUBMITTED")
    state = apply_execution_event(state, "ENTRY_FILLED", fill_quantity=Decimal("1.0"))
    state = apply_execution_event(state, "EXIT_FILLED")

    assert state.position_status == "CLOSED"
    assert state.order_status == "CLOSED"
    assert state.allow_new_entries is True
