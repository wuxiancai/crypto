import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.paper.trading import PaperFill, PaperPosition, PaperSnapshot


def paper_snapshot_to_payload(snapshot: PaperSnapshot) -> dict[str, Any]:
    return {
        "equity": str(snapshot.equity),
        "open_position": _position_to_payload(snapshot.open_position),
        "fills": [_fill_to_payload(fill) for fill in snapshot.fills],
        "rejected_signals": snapshot.rejected_signals,
    }


def paper_snapshot_from_payload(payload: dict[str, Any]) -> PaperSnapshot:
    return PaperSnapshot(
        equity=Decimal(payload["equity"]),
        open_position=_position_from_payload(payload["open_position"]),
        fills=[_fill_from_payload(fill) for fill in payload["fills"]],
        rejected_signals=int(payload["rejected_signals"]),
    )


def save_paper_snapshot(snapshot: PaperSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(paper_snapshot_to_payload(snapshot), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_paper_snapshot(path: Path) -> PaperSnapshot | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return paper_snapshot_from_payload(payload)


def _position_to_payload(position: PaperPosition | None) -> dict[str, Any] | None:
    if position is None:
        return None
    return {
        "symbol": position.symbol,
        "side": position.side,
        "strategy_type": position.strategy_type,
        "entry_time": position.entry_time,
        "entry_price": str(position.entry_price),
        "stop_loss": str(position.stop_loss),
        "take_profit": str(position.take_profit),
        "quantity": str(position.quantity),
        "entry_fee": str(position.entry_fee),
    }


def _position_from_payload(payload: dict[str, Any] | None) -> PaperPosition | None:
    if payload is None:
        return None
    return PaperPosition(
        symbol=payload["symbol"],
        side=payload["side"],
        strategy_type=payload["strategy_type"],
        entry_time=int(payload["entry_time"]),
        entry_price=Decimal(payload["entry_price"]),
        stop_loss=Decimal(payload["stop_loss"]),
        take_profit=Decimal(payload["take_profit"]),
        quantity=Decimal(payload["quantity"]),
        entry_fee=Decimal(payload["entry_fee"]),
    )


def _fill_to_payload(fill: PaperFill) -> dict[str, Any]:
    return {
        "symbol": fill.symbol,
        "side": fill.side,
        "strategy_type": fill.strategy_type,
        "entry_time": fill.entry_time,
        "exit_time": fill.exit_time,
        "entry_price": str(fill.entry_price),
        "exit_price": str(fill.exit_price),
        "quantity": str(fill.quantity),
        "gross_pnl": str(fill.gross_pnl),
        "fees": str(fill.fees),
        "net_pnl": str(fill.net_pnl),
        "exit_reason": fill.exit_reason,
    }


def _fill_from_payload(payload: dict[str, Any]) -> PaperFill:
    return PaperFill(
        symbol=payload["symbol"],
        side=payload["side"],
        strategy_type=payload["strategy_type"],
        entry_time=int(payload["entry_time"]),
        exit_time=int(payload["exit_time"]),
        entry_price=Decimal(payload["entry_price"]),
        exit_price=Decimal(payload["exit_price"]),
        quantity=Decimal(payload["quantity"]),
        gross_pnl=Decimal(payload["gross_pnl"]),
        fees=Decimal(payload["fees"]),
        net_pnl=Decimal(payload["net_pnl"]),
        exit_reason=payload["exit_reason"],
    )
