from dataclasses import dataclass
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
    signal_level: str | None = None
    score: Decimal | None = None


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
    signal_level = getattr(signal, "signal_level", None)
    score = getattr(signal, "score", None)
    return StrategySignal(
        action=signal.action,
        strategy_type=signal.strategy_type,
        signal_level=signal_level,
        score=score,
        reason=signal.reason,
    )


def _wait(reason: list[str]) -> StrategySignal:
    return StrategySignal(action="WAIT", strategy_type="SYSTEM", reason=reason)
