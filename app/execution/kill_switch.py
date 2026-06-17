from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class KillSwitchState:
    is_active: bool
    allow_new_entries: bool
    close_positions: bool
    operator: str
    reason: str
    triggered_at: datetime
    released_by: str | None = None
    released_at: datetime | None = None


def activate_kill_switch(
    operator: str,
    reason: str,
    close_positions: bool,
    triggered_at: datetime | None = None,
) -> KillSwitchState:
    if not operator or not reason:
        raise ValueError("operator and reason are required")
    return KillSwitchState(
        is_active=True,
        allow_new_entries=False,
        close_positions=close_positions,
        operator=operator,
        reason=reason,
        triggered_at=triggered_at or datetime.now(timezone.utc),
    )


def release_kill_switch(
    state: KillSwitchState,
    operator: str,
    released_at: datetime | None = None,
) -> KillSwitchState:
    if not operator:
        raise ValueError("operator is required")
    return KillSwitchState(
        is_active=False,
        allow_new_entries=True,
        close_positions=False,
        operator=state.operator,
        reason=state.reason,
        triggered_at=state.triggered_at,
        released_by=operator,
        released_at=released_at or datetime.now(timezone.utc),
    )
