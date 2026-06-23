import asyncio
from decimal import Decimal


def test_sync_klines_defaults_include_layered_strategy_intervals():
    from scripts.sync_klines import DEFAULT_SYNC_INTERVALS, parse_args

    assert DEFAULT_SYNC_INTERVALS == ("1d", "4h", "1h", "15m")
    args = parse_args([])
    assert args.intervals == ["1d", "4h", "1h", "15m"]


def test_sync_klines_dry_run_fetches_each_symbol_interval_without_writing(monkeypatch, capsys):
    from app.data.quality import INTERVAL_MS, Kline
    import scripts.sync_klines as sync

    fetched: list[tuple[str, str, int]] = []

    async def fake_fetch_klines(symbol, interval, limit, settings):
        fetched.append((symbol, interval, limit))
        return [
            Kline(
                symbol=symbol,
                interval=interval,
                open_time=0,
                close_time=INTERVAL_MS[interval] - 1,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("10"),
            )
        ]

    def fail_build_session_factory(_settings):
        raise AssertionError("dry-run must not build a database session")

    monkeypatch.setattr(sync, "fetch_klines", fake_fetch_klines)
    monkeypatch.setattr(sync, "build_session_factory", fail_build_session_factory)

    asyncio.run(sync.sync_klines(["BTCUSDT", "ETHUSDT"], ["1d", "15m"], limit=3, dry_run=True))

    assert fetched == [
        ("BTCUSDT", "1d", 3),
        ("BTCUSDT", "15m", 3),
        ("ETHUSDT", "1d", 3),
        ("ETHUSDT", "15m", 3),
    ]
    output = capsys.readouterr().out
    assert "DRY-RUN BTCUSDT 1d: fetched 1 closed klines" in output
    assert "DRY-RUN ETHUSDT 15m: fetched 1 closed klines" in output


def test_sync_klines_reports_database_write_failure(monkeypatch):
    import pytest
    from sqlalchemy.exc import OperationalError

    from app.data.quality import INTERVAL_MS, Kline
    import scripts.sync_klines as sync

    async def fake_fetch_klines(symbol, interval, limit, settings):
        return [
            Kline(
                symbol=symbol,
                interval=interval,
                open_time=0,
                close_time=INTERVAL_MS[interval] - 1,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("10"),
            )
        ]

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_build_session_factory(_settings):
        return lambda: FakeSession()

    def fake_upsert_klines(_session, _rows):
        raise OperationalError("select 1", {}, RuntimeError("connection refused"))

    monkeypatch.setattr(sync, "fetch_klines", fake_fetch_klines)
    monkeypatch.setattr(sync, "build_session_factory", fake_build_session_factory)
    monkeypatch.setattr(sync, "upsert_klines", fake_upsert_klines)

    with pytest.raises(RuntimeError, match="failed to write klines to DATABASE_URL"):
        asyncio.run(sync.sync_klines(["BTCUSDT"], ["1d"], limit=1, dry_run=False))
