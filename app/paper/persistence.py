import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.paper.trading import PaperFill, PaperPosition, PaperSignalEvaluation, PaperSnapshot


def paper_snapshot_to_payload(snapshot: PaperSnapshot) -> dict[str, Any]:
    return {
        "equity": str(snapshot.equity),
        "open_position": _position_to_payload(snapshot.open_position),
        "open_positions": [_position_to_payload(position) for position in snapshot.open_positions],
        "fills": [_fill_to_payload(fill) for fill in snapshot.fills],
        "rejected_signals": snapshot.rejected_signals,
        "runtime_started_at_ms": snapshot.runtime_started_at_ms,
        "last_update_at_ms": snapshot.last_update_at_ms,
        "signal_evaluations": [
            _signal_evaluation_to_payload(evaluation)
            for evaluation in (snapshot.signal_evaluations or [])
        ],
    }


def paper_snapshot_from_payload(payload: dict[str, Any]) -> PaperSnapshot:
    open_positions = [
        position
        for position in (
            _position_from_payload(position_payload)
            for position_payload in payload.get("open_positions", [])
        )
        if position is not None
    ]
    legacy_open_position = _position_from_payload(payload.get("open_position"))
    if not open_positions and legacy_open_position is not None:
        open_positions = [legacy_open_position]
    return PaperSnapshot(
        equity=Decimal(payload["equity"]),
        open_position=open_positions[0] if open_positions else None,
        open_positions=open_positions,
        fills=[_fill_from_payload(fill) for fill in payload["fills"]],
        rejected_signals=int(payload["rejected_signals"]),
        runtime_started_at_ms=payload.get("runtime_started_at_ms"),
        last_update_at_ms=payload.get("last_update_at_ms"),
        signal_evaluations=[
            _signal_evaluation_from_payload(evaluation)
            for evaluation in payload.get("signal_evaluations", [])
        ],
    )


def save_paper_snapshot(snapshot: PaperSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = paper_snapshot_to_payload(snapshot)
    existing_payload = _read_existing_state_payload(path)
    preserved_fields = _read_preserved_state_fields(existing_payload)
    payload.update(preserved_fields)
    if not payload.get("signal_evaluations"):
        existing_signal_evaluations = existing_payload.get("signal_evaluations")
        if isinstance(existing_signal_evaluations, list) and existing_signal_evaluations:
            payload["signal_evaluations"] = existing_signal_evaluations
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_paper_snapshot(path: Path) -> PaperSnapshot | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return paper_snapshot_from_payload(payload)


def _read_existing_state_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_preserved_state_fields(payload: dict[str, Any]) -> dict[str, Any]:
    preserved: dict[str, Any] = {}
    prices = payload.get("market_prices")
    if isinstance(prices, dict):
        preserved["market_prices"] = prices
    strategy_details = payload.get("strategy_details")
    if isinstance(strategy_details, list):
        preserved["strategy_details"] = strategy_details
    return preserved


def _position_to_payload(position: PaperPosition | None) -> dict[str, Any] | None:
    if position is None:
        return None
    return {
        "symbol": position.symbol,
        "interval": position.interval,
        "side": position.side,
        "strategy_type": position.strategy_type,
        "bucket": position.bucket,
        "entry_time": position.entry_time,
        "entry_price": str(position.entry_price),
        "stop_loss": str(position.stop_loss),
        "take_profit": str(position.take_profit),
        "quantity": str(position.quantity),
        "entry_fee": str(position.entry_fee),
        "leverage": str(position.leverage),
        "initial_stop_loss": str(position.initial_stop_loss or position.stop_loss),
        "trailing_active": position.trailing_active,
    }


def _position_from_payload(payload: dict[str, Any] | None) -> PaperPosition | None:
    if payload is None:
        return None
    return PaperPosition(
        symbol=payload["symbol"],
        interval=payload.get("interval", "15m"),
        side=payload["side"],
        strategy_type=payload["strategy_type"],
        bucket=payload.get("bucket", "LEGACY"),
        entry_time=int(payload["entry_time"]),
        entry_price=Decimal(payload["entry_price"]),
        stop_loss=Decimal(payload["stop_loss"]),
        take_profit=Decimal(payload["take_profit"]),
        quantity=Decimal(payload["quantity"]),
        entry_fee=Decimal(payload["entry_fee"]),
        leverage=Decimal(payload.get("leverage", "10")),
        initial_stop_loss=Decimal(payload.get("initial_stop_loss", payload["stop_loss"])),
        trailing_active=bool(payload.get("trailing_active", False)),
    )


def _fill_to_payload(fill: PaperFill) -> dict[str, Any]:
    return {
        "symbol": fill.symbol,
        "side": fill.side,
        "strategy_type": fill.strategy_type,
        "bucket": fill.bucket,
        "entry_time": fill.entry_time,
        "exit_time": fill.exit_time,
        "entry_price": str(fill.entry_price),
        "exit_price": str(fill.exit_price),
        "quantity": str(fill.quantity),
        "leverage": str(fill.leverage),
        "gross_pnl": str(fill.gross_pnl),
        "fees": str(fill.fees),
        "funding_fee": str(fill.funding_fee),
        "net_pnl": str(fill.net_pnl),
        "exit_reason": fill.exit_reason,
        "exit_detail": fill.exit_detail,
    }


def _fill_from_payload(payload: dict[str, Any]) -> PaperFill:
    return PaperFill(
        symbol=payload["symbol"],
        side=payload["side"],
        strategy_type=payload["strategy_type"],
        bucket=payload.get("bucket", "LEGACY"),
        entry_time=int(payload["entry_time"]),
        exit_time=int(payload["exit_time"]),
        entry_price=Decimal(payload["entry_price"]),
        exit_price=Decimal(payload["exit_price"]),
        quantity=Decimal(payload["quantity"]),
        leverage=Decimal(payload.get("leverage", "10")),
        gross_pnl=Decimal(payload["gross_pnl"]),
        fees=Decimal(payload["fees"]),
        funding_fee=Decimal(payload.get("funding_fee", "0")),
        net_pnl=Decimal(payload["net_pnl"]),
        exit_reason=payload["exit_reason"],
        exit_detail=payload.get("exit_detail", ""),
    )


def _signal_evaluation_to_payload(evaluation: PaperSignalEvaluation) -> dict[str, Any]:
    return {
        "evaluated_at_ms": evaluation.evaluated_at_ms,
        "symbol": evaluation.symbol,
        "interval": evaluation.interval,
        "close": str(evaluation.close),
        "action": evaluation.action,
        "strategy_type": evaluation.strategy_type,
        "reason": list(evaluation.reason),
        "core_rules": list(evaluation.core_rules),
        "chart_points": list(evaluation.chart_points),
        "chart_timeframes": {
            interval: list(points)
            for interval, points in evaluation.chart_timeframes.items()
        },
        "condition_statuses": list(evaluation.condition_statuses),
        "nearest_strategy": evaluation.nearest_strategy,
    }


def _signal_evaluation_from_payload(payload: dict[str, Any]) -> PaperSignalEvaluation:
    return PaperSignalEvaluation(
        evaluated_at_ms=int(payload["evaluated_at_ms"]),
        symbol=payload["symbol"],
        interval=payload["interval"],
        close=Decimal(payload["close"]),
        action=payload["action"],
        strategy_type=payload["strategy_type"],
        reason=tuple(payload.get("reason", [])),
        core_rules=tuple(payload.get("core_rules", [])),
        chart_points=tuple(payload.get("chart_points", [])),
        chart_timeframes={
            interval: tuple(points)
            for interval, points in payload.get("chart_timeframes", {}).items()
        },
        condition_statuses=tuple(payload.get("condition_statuses", [])),
        nearest_strategy=payload.get("nearest_strategy", {}),
    )
