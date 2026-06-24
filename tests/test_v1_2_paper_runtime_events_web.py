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
    assert "策略信号：1" in html
    assert "成交：1" in html
    assert 'href="/paper/events?event_type=fill"' in html
    assert 'href="/paper/events?event_type=rejected_signal"' in html
    assert "净盈亏=25.50, 退出原因=止盈, 数量=0.0100" in html
    assert "是否开仓=是, 原因=日线空头" in html
    assert "日线核心做空 (SHORT_DAY_CORE)" in html
    assert "做空入场 (SHORT_ENTRY)" in html
    assert "日线核心仓 (DAY_CORE)" in html


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


def test_paper_runtime_events_page_shows_payload_details():
    from types import SimpleNamespace

    from app.paper.web_status import render_paper_runtime_events_html

    html = render_paper_runtime_events_html(
        [
            SimpleNamespace(
                event_time=1_800_000,
                event_type="signal",
                symbol="BTCUSDT",
                interval="15m",
                strategy_type="SHORT_DAY_CORE",
                action="SHORT_ENTRY",
                bucket="DAY_CORE",
                payload=(
                    '{"reason":["daily bearish"],'
                    '"condition_statuses":[{"name":"15m bearish confirmation","passed":true}],'
                    '"opened_position":{"side":"SHORT","entry_price":"64000"}}'
                ),
            )
        ],
        filters={},
    )

    assert "<details" in html
    assert "完整原始数据" in html
    assert "15m bearish confirmation" in html
    assert "entry_price" in html


def test_loads_paper_runtime_events_for_web_with_time_range():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    from app.database.models import Base
    from app.database.repositories import record_paper_runtime_event
    from scripts.run_paper_status_web import _load_paper_runtime_events_for_web

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with Session(engine) as session:
        for event_time, symbol in ((1_800_000, "BTCUSDT"), (3_600_000, "ETHUSDT")):
            record_paper_runtime_event(
                session,
                event_type="signal",
                symbol=symbol,
                interval="15m",
                event_time=event_time,
                strategy_type="SYSTEM",
                action="WAIT",
                bucket=None,
                payload={"reason": [symbol]},
            )

    events = _load_paper_runtime_events_for_web(
        {
            "limit": ["10"],
            "start_time": ["1970-01-01 08:30"],
            "end_time": ["1970-01-01 08:59"],
        },
        session_factory=session_factory,
    )

    assert [event.symbol for event in events] == ["BTCUSDT"]


def test_paper_runtime_events_page_links_fill_to_prior_signal_timeline():
    from types import SimpleNamespace

    from app.paper.web_status import render_paper_runtime_events_html

    html = render_paper_runtime_events_html(
        [
            SimpleNamespace(
                event_time=1_800_000,
                event_type="signal",
                symbol="BTCUSDT",
                interval="15m",
                strategy_type="SHORT_DAY_CORE",
                action="SHORT_ENTRY",
                bucket="DAY_CORE",
                payload='{"reason":["daily bearish"],"opened_position":{"side":"SHORT","entry_price":"64000"}}',
            ),
            SimpleNamespace(
                event_time=2_100_000,
                event_type="snapshot",
                symbol="BTCUSDT",
                interval="15m",
                strategy_type="SYSTEM",
                action="SNAPSHOT",
                bucket=None,
                payload='{"equity":"1005","open_positions":[{"strategy_type":"SHORT_DAY_CORE"}],"rejected_signals":0}',
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
        ],
        filters={},
    )

    assert "交易时间线" in html
    assert "BTCUSDT SHORT_DAY_CORE DAY_CORE" in html
    assert "开仓信号：是否开仓=是, 原因=日线空头" in html
    assert "持仓快照：账户权益=1005.00, 持仓数=1, 累计拒绝=0" in html
    assert "退出成交：净盈亏=25.50, 退出原因=止盈, 数量=0.0100" in html
