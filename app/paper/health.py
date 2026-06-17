from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PaperRuntimeSnapshot:
    websocket_connected: bool
    seconds_since_last_kline: int
    max_kline_delay_seconds: int
    equity: Decimal
    initial_equity: Decimal
    max_drawdown_pct: Decimal
    rejected_signals: int
    max_rejected_signals: int
    runtime_errors: int
    max_runtime_errors: int

    @classmethod
    def safe_defaults(cls, **overrides: object) -> "PaperRuntimeSnapshot":
        values = {
            "websocket_connected": True,
            "seconds_since_last_kline": 5,
            "max_kline_delay_seconds": 30,
            "equity": Decimal("1000"),
            "initial_equity": Decimal("1000"),
            "max_drawdown_pct": Decimal("0.05"),
            "rejected_signals": 0,
            "max_rejected_signals": 10,
            "runtime_errors": 0,
            "max_runtime_errors": 0,
        }
        values.update(overrides)
        return cls(**values)


@dataclass(frozen=True)
class PaperHealthResult:
    is_healthy: bool
    status: str
    reasons: tuple[str, ...]


def evaluate_paper_health(snapshot: PaperRuntimeSnapshot) -> PaperHealthResult:
    reasons: list[str] = []

    if not snapshot.websocket_connected:
        reasons.append("websocket_disconnected")
    if snapshot.seconds_since_last_kline > snapshot.max_kline_delay_seconds:
        reasons.append("market_data_stale")
    if _drawdown_pct(snapshot.equity, snapshot.initial_equity) > snapshot.max_drawdown_pct:
        reasons.append("paper_drawdown_exceeded")
    if snapshot.rejected_signals > snapshot.max_rejected_signals:
        reasons.append("too_many_rejected_signals")
    if snapshot.runtime_errors > snapshot.max_runtime_errors:
        reasons.append("runtime_errors_present")

    return PaperHealthResult(
        is_healthy=not reasons,
        status="HEALTHY" if not reasons else "UNHEALTHY",
        reasons=tuple(reasons),
    )


def _drawdown_pct(equity: Decimal, initial_equity: Decimal) -> Decimal:
    if initial_equity <= 0 or equity >= initial_equity:
        return Decimal("0")
    return (initial_equity - equity) / initial_equity
