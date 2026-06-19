from decimal import Decimal
import asyncio


def test_database_metadata_contains_v0_1_tables():
    from sqlalchemy import BigInteger

    from app.database.models import Base

    table_names = set(Base.metadata.tables)

    assert {
        "symbols",
        "klines",
        "indicator_snapshots",
        "config_snapshots",
    }.issubset(table_names)

    indicator_columns = set(Base.metadata.tables["indicator_snapshots"].columns.keys())
    assert {"di_plus", "di_minus"}.issubset(indicator_columns)
    assert isinstance(Base.metadata.tables["klines"].columns["open_time"].type, BigInteger)
    assert isinstance(Base.metadata.tables["klines"].columns["close_time"].type, BigInteger)
    assert isinstance(Base.metadata.tables["indicator_snapshots"].columns["open_time"].type, BigInteger)


def test_binance_kline_payload_parses_to_closed_decimal_kline():
    from app.data.binance import parse_binance_kline

    payload = [
        0,
        "100.00",
        "110.00",
        "95.00",
        "105.00",
        "12.500",
        899_999,
        "1312.50",
        42,
        "6.100",
        "640.50",
        "0",
    ]

    row = parse_binance_kline("BTCUSDT", "15m", payload)

    assert row.symbol == "BTCUSDT"
    assert row.interval == "15m"
    assert row.open == Decimal("100.00")
    assert row.close == Decimal("105.00")
    assert row.volume == Decimal("12.500")
    assert row.is_closed is True


def test_fetch_klines_retries_timeout_before_success(monkeypatch):
    import httpx

    from app.config.settings import Settings
    from app.data import binance
    from app.data.binance import fetch_klines

    attempts = 0
    sleeps: list[float] = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [[0, "100", "101", "99", "100", "10", 899_999]]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise httpx.ConnectTimeout("connect timed out")
            return FakeResponse()

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(binance.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(binance.asyncio, "sleep", fake_sleep)

    rows = asyncio.run(
        fetch_klines(
            "BTCUSDT",
            "15m",
            settings=Settings(binance_base_url="https://fapi.binance.com"),
        )
    )

    assert attempts == 3
    assert sleeps == [0.2, 0.4]
    assert rows[0].symbol == "BTCUSDT"


def test_fetch_klines_retries_http_503_with_backoff(monkeypatch):
    import httpx

    from app.config.settings import Settings
    from app.data import binance
    from app.data.binance import fetch_klines

    attempts = 0
    sleeps: list[float] = []

    class FakeResponse:
        def __init__(self, status_code: int):
            self.status_code = status_code
            self.request = httpx.Request("GET", "https://fapi.binance.com/fapi/v1/klines")

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("service unavailable", request=self.request, response=self)

        def json(self):
            return [[0, "100", "101", "99", "100", "10", 899_999]]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            return FakeResponse(503 if attempts == 1 else 200)

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(binance.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(binance.asyncio, "sleep", fake_sleep)

    rows = asyncio.run(
        fetch_klines(
            "BTCUSDT",
            "15m",
            settings=Settings(binance_base_url="https://fapi.binance.com"),
        )
    )

    assert attempts == 2
    assert sleeps == [0.2]
    assert rows[0].close == Decimal("100")
