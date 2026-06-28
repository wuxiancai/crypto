from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol


class EntryCandidate(Protocol):
    action: str
    strategy_type: str
    reason: list[str]


@dataclass(frozen=True)
class StrategySignal:
    action: str
    strategy_type: str
    reason: list[str]
    bucket: str | None = None
    entry_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    risk_reward: Decimal | None = None
    signal_level: str | None = None
    score: Decimal | None = None
    risk_pct: Decimal | None = None
    risk_multiplier: Decimal = Decimal("1")
    trailing_atr: Decimal | None = None
    max_standard_position_pct: Decimal | None = None
    core_rules: list[str] = field(default_factory=list)
    chart_points: list[dict[str, str]] = field(default_factory=list)
    chart_timeframes: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    condition_statuses: list[dict[str, object]] = field(default_factory=list)
    nearest_strategy: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalInputs:
    data_ready: bool = True
    risk_allows_new_entries: bool = True
    exit_signal: StrategySignal | None = None
    main_signal: EntryCandidate | None = None
    reversal_signal: EntryCandidate | None = None


def select_signal(inputs: SignalInputs) -> StrategySignal:
    if not inputs.data_ready:
        return _wait(["data not ready"])
    if _is_active(inputs.exit_signal):
        return inputs.exit_signal
    if not inputs.risk_allows_new_entries:
        return _wait(["risk blocked before new entries"])
    if _is_active(inputs.main_signal):
        return _from_candidate(inputs.main_signal)
    if _is_active(inputs.reversal_signal):
        return _from_candidate(inputs.reversal_signal)
    return _wait(["no actionable signal"])


def _is_active(signal: EntryCandidate | None) -> bool:
    return signal is not None and signal.action != "WAIT"


def _from_candidate(signal: EntryCandidate) -> StrategySignal:
    return StrategySignal(
        action=signal.action,
        strategy_type=signal.strategy_type,
        bucket=getattr(signal, "bucket", None),
        entry_price=getattr(signal, "entry_price", None),
        stop_loss=getattr(signal, "stop_loss", None),
        take_profit=getattr(signal, "take_profit", None),
        risk_reward=getattr(signal, "risk_reward", None),
        signal_level=getattr(signal, "signal_level", None),
        score=getattr(signal, "score", None),
        risk_pct=getattr(signal, "risk_pct", None),
        risk_multiplier=getattr(signal, "risk_multiplier", Decimal("1")),
        trailing_atr=getattr(signal, "trailing_atr", None) or getattr(signal, "atr", None),
        max_standard_position_pct=getattr(signal, "max_standard_position_pct", None),
        reason=signal.reason,
    )


def _wait(reason: list[str]) -> StrategySignal:
    return StrategySignal(action="WAIT", strategy_type="SYSTEM", reason=reason)
