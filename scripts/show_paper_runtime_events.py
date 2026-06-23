from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.db import build_session_factory
from app.database.models import PaperRuntimeEvent

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def load_paper_runtime_events(
    session,
    *,
    limit: int = 50,
    event_type: str | None = None,
    symbol: str | None = None,
    strategy_type: str | None = None,
    bucket: str | None = None,
    start_time_ms: int | None = None,
    end_time_ms: int | None = None,
) -> list[PaperRuntimeEvent]:
    query = select(PaperRuntimeEvent).order_by(PaperRuntimeEvent.id.desc()).limit(max(1, limit))
    if event_type:
        query = query.where(PaperRuntimeEvent.event_type == event_type)
    if symbol:
        query = query.where(PaperRuntimeEvent.symbol == symbol)
    if strategy_type:
        query = query.where(PaperRuntimeEvent.strategy_type == strategy_type)
    if bucket:
        query = query.where(PaperRuntimeEvent.bucket == bucket)
    if start_time_ms is not None:
        query = query.where(PaperRuntimeEvent.event_time >= start_time_ms)
    if end_time_ms is not None:
        query = query.where(PaperRuntimeEvent.event_time <= end_time_ms)
    return list(session.execute(query).scalars().all())


def format_paper_runtime_events(events: list[PaperRuntimeEvent]) -> str:
    if not events:
        return "暂无 Paper Runtime 复盘事件"
    headers = ("时间 UTC+8", "类型", "交易对", "周期", "策略", "动作", "Bucket", "摘要")
    rows = [
        (
            _format_event_time(event.event_time),
            event.event_type,
            event.symbol,
            event.interval,
            event.strategy_type,
            event.action,
            event.bucket or "-",
            _event_summary(event),
        )
        for event in events
    ]
    widths = [
        max(len(str(row[index])) for row in (headers, *rows))
        for index in range(len(headers))
    ]
    lines = [
        " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(headers)),
        "-+-".join("-" * width for width in widths),
    ]
    lines.extend(
        " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def _event_summary(event: PaperRuntimeEvent) -> str:
    payload = _decode_payload(event.payload)
    if event.event_type == "fill":
        return (
            f"net={payload.get('net_pnl', '-')}, "
            f"exit={payload.get('exit_reason', '-')}, "
            f"qty={payload.get('quantity', '-')}"
        )
    if event.event_type == "rejected_signal":
        return f"reason={','.join(payload.get('reason', []) or []) or '-'}"
    if event.event_type == "snapshot":
        return (
            f"equity={payload.get('equity', '-')}, "
            f"positions={len(payload.get('open_positions', []) or [])}, "
            f"rejected={payload.get('rejected_signals', 0)}"
        )
    if event.event_type == "signal":
        opened = payload.get("opened_position")
        opened_label = "yes" if opened else "no"
        return f"opened={opened_label}, reason={','.join(payload.get('reason', []) or []) or '-'}"
    return "-"


def _decode_payload(payload: str) -> dict:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _format_event_time(event_time: int) -> str:
    return datetime.fromtimestamp(event_time / 1000, tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show recent Paper Trading runtime replay events.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--event-type", choices=["signal", "rejected_signal", "fill", "snapshot"])
    parser.add_argument("--symbol")
    parser.add_argument("--strategy-type")
    parser.add_argument("--bucket")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    session_factory = build_session_factory()
    with session_factory() as session:
        events = load_paper_runtime_events(
            session,
            limit=args.limit,
            event_type=args.event_type,
            symbol=args.symbol,
            strategy_type=args.strategy_type,
            bucket=args.bucket,
        )
    print(format_paper_runtime_events(events))


if __name__ == "__main__":
    main()
