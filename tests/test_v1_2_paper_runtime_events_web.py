def test_renders_paper_runtime_events_page():
    from types import SimpleNamespace

    from app.paper.web_status import render_paper_runtime_events_html

    events = [
        SimpleNamespace(
            event_time=1_800_000,
            event_type="signal",
            symbol="BTCUSDT",
            interval="15m",
            strategy_type="SHORT_DAY_CORE",
            action="SHORT_ENTRY",
            bucket="DAY_CORE",
            payload='{"reason":["daily bearish"],"opened_position":{"side":"SHORT"}}',
        ),
        SimpleNamespace(
            event_time=2_700_000,
            event_type="fill",
            symbol="BTCUSDT",
            interval="15m",
            strategy_type="SHORT_DAY_CORE",
            action="EXIT",
            bucket="DAY_CORE",
            payload='{"net_pnl":"25.50","exit_reason":"TAKE_PROFIT","quantity":"0.01"}',
        ),
    ]

    html = render_paper_runtime_events_html(
        events,
        filters={
            "limit": "20",
            "symbol": "BTCUSDT",
            "event_type": "fill",
            "strategy_type": "SHORT_DAY_CORE",
            "bucket": "DAY_CORE",
        },
    )

    assert "Paper 复盘" in html
    assert 'action="/paper/events"' in html
    assert 'name="event_type"' in html
    assert 'value="BTCUSDT"' in html
    assert "SHORT_DAY_CORE" in html
    assert "DAY_CORE" in html
    assert "net=25.50, exit=TAKE_PROFIT, qty=0.01" in html
    assert "opened=yes, reason=daily bearish" in html


def test_loads_paper_runtime_events_for_web_with_filters():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    from app.database.models import Base
    from app.database.repositories import record_paper_runtime_event
    from scripts.run_paper_status_web import _load_paper_runtime_events_for_web

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

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
            payload={"reason": ["daily bearish"]},
        )
        record_paper_runtime_event(
            session,
            event_type="snapshot",
            symbol="ETHUSDT",
            interval="15m",
            event_time=1_800_000,
            strategy_type="SYSTEM",
            action="SNAPSHOT",
            bucket=None,
            payload={"equity": "1000"},
        )

    events = _load_paper_runtime_events_for_web(
        {
            "limit": ["10"],
            "symbol": ["BTCUSDT"],
            "bucket": ["DAY_CORE"],
        },
        session_factory=session_factory,
    )

    assert len(events) == 1
    assert events[0].symbol == "BTCUSDT"
    assert events[0].bucket == "DAY_CORE"
