from dataclasses import dataclass
from decimal import Decimal

from app.paper.trading import PaperSnapshot


@dataclass(frozen=True)
class AlertConfig:
    initial_equity: Decimal
    max_drawdown_pct: Decimal
    max_rejected_signals: int


@dataclass(frozen=True)
class Alert:
    level: str
    code: str
    message: str


def evaluate_paper_alerts(snapshot: PaperSnapshot, config: AlertConfig) -> list[Alert]:
    alerts: list[Alert] = []
    drawdown_pct = _drawdown_pct(snapshot.equity, config.initial_equity)
    if drawdown_pct >= config.max_drawdown_pct:
        alerts.append(
            Alert(
                level="WARN",
                code="PAPER_DRAWDOWN",
                message=f"paper drawdown {drawdown_pct} reached threshold {config.max_drawdown_pct}",
            )
        )
    if snapshot.rejected_signals > config.max_rejected_signals:
        alerts.append(
            Alert(
                level="WARN",
                code="PAPER_REJECTED_SIGNALS",
                message=f"paper rejected signals {snapshot.rejected_signals} exceeded {config.max_rejected_signals}",
            )
        )
    return alerts


def _drawdown_pct(equity: Decimal, initial_equity: Decimal) -> Decimal:
    if initial_equity <= 0 or equity >= initial_equity:
        return Decimal("0")
    return (initial_equity - equity) / initial_equity
