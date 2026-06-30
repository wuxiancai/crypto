def test_formats_paper_runtime_events_for_replay_cli():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.database.models import Base
    from app.database.repositories import record_paper_runtime_event
    from scripts.show_paper_runtime_events import format_paper_runtime_events, load_paper_runtime_events

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        record_paper_runtime_event(
            session,
            event_type="signal",
            symbol="BTCUSDT",
            interval="15m",
            event_time=1_800_000,
            strategy_type="SHORT_DAY_CORE",
            action="SHORT_ENTRY",
            bucket="DAY_CORE",
            payload={"reason": ["daily bearish"], "opened_position": {"side": "SHORT"}},
        )
        record_paper_runtime_event(
            session,
            event_type="fill",
            symbol="BTCUSDT",
            interval="15m",
            event_time=2_700_000,
            strategy_type="SHORT_DAY_CORE",
            action="EXIT",
            bucket="DAY_CORE",
            payload={"net_pnl": "25.50", "exit_reason": "TAKE_PROFIT", "quantity": "0.01"},
        )
        events = load_paper_runtime_events(session, limit=10, symbol="BTCUSDT", bucket="DAY_CORE")

    table = format_paper_runtime_events(events)

    assert "Paper Runtime" not in table
    assert "SHORT_DAY_CORE" in table
    assert "net=25.50, exit=TAKE_PROFIT, qty=0.01" in table
    assert "opened=yes, reason=daily bearish" in table


def test_formats_empty_paper_runtime_events():
    from scripts.show_paper_runtime_events import format_paper_runtime_events

    assert format_paper_runtime_events([]) == "暂无 Paper Runtime 复盘事件（可按层级过滤）"
