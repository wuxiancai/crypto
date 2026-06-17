from datetime import datetime, timezone


def test_kill_switch_activation_blocks_new_entries_and_records_audit_fields():
    from app.execution.kill_switch import activate_kill_switch

    triggered_at = datetime(2026, 6, 18, 9, 30, tzinfo=timezone.utc)

    state = activate_kill_switch(
        operator="risk-admin",
        reason="daily loss limit reached",
        close_positions=True,
        triggered_at=triggered_at,
    )

    assert state.is_active is True
    assert state.allow_new_entries is False
    assert state.close_positions is True
    assert state.operator == "risk-admin"
    assert state.reason == "daily loss limit reached"
    assert state.triggered_at == triggered_at


def test_kill_switch_requires_operator_and_reason_for_audit():
    from app.execution.kill_switch import activate_kill_switch

    try:
        activate_kill_switch(operator="", reason="", close_positions=False)
    except ValueError as exc:
        assert str(exc) == "operator and reason are required"
    else:
        raise AssertionError("expected kill switch audit validation error")


def test_kill_switch_can_be_released_by_operator():
    from app.execution.kill_switch import activate_kill_switch, release_kill_switch

    state = activate_kill_switch(
        operator="risk-admin",
        reason="manual drill",
        close_positions=False,
    )
    released = release_kill_switch(state, operator="risk-admin")

    assert released.is_active is False
    assert released.allow_new_entries is True
    assert released.released_by == "risk-admin"
