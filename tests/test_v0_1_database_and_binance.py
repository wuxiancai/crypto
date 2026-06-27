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
        "paper_runtime_events",
    }.issubset(table_names)

    indicator_columns = set(Base.metadata.tables["indicator_snapshots"].columns.keys())
    config_columns = set(Base.metadata.tables["config_snapshots"].columns.keys())
    assert {"di_plus", "di_minus"}.issubset(indicator_columns)
    assert "content" in config_columns
    assert isinstance(Base.metadata.tables["klines"].columns["open_time"].type, BigInteger)
    assert isinstance(Base.metadata.tables["klines"].columns["close_time"].type, BigInteger)
    assert isinstance(Base.metadata.tables["indicator_snapshots"].columns["open_time"].type, BigInteger)
    assert isinstance(Base.metadata.tables["paper_runtime_events"].columns["event_time"].type, BigInteger)


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


def test_binance_premium_index_payload_parses_funding_snapshot():
    from app.data.binance import parse_binance_premium_index

    snapshot = parse_binance_premium_index(
        {
            "symbol": "BTCUSDT",
            "lastFundingRate": "0.00038246",
            "nextFundingTime": 1_597_392_000_000,
            "time": 1_597_370_495_002,
        }
    )

    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.last_funding_rate == Decimal("0.00038246")
    assert snapshot.next_funding_time == 1_597_392_000_000
    assert snapshot.event_time == 1_597_370_495_002


def test_fetch_funding_snapshots_reads_mark_price_endpoint(monkeypatch):
    from app.config.settings import Settings
    from app.data import binance
    from app.data.binance import fetch_funding_snapshots

    requests: list[tuple[str, dict[str, str]]] = []

    class FakeResponse:
        status_code = 200

        def __init__(self, symbol: str):
            self._symbol = symbol

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "symbol": self._symbol,
                "lastFundingRate": "0.0005",
                "nextFundingTime": 1_597_392_000_000,
                "time": 1_597_370_495_002,
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, path, params):
            requests.append((path, params))
            return FakeResponse(str(params["symbol"]))

    monkeypatch.setattr(binance.httpx, "AsyncClient", FakeClient)

    snapshots = asyncio.run(
        fetch_funding_snapshots(
            ("BTCUSDT", "ETHUSDT"),
            settings=Settings(binance_base_url="https://fapi.binance.com"),
        )
    )

    assert requests == [
        ("/fapi/v1/premiumIndex", {"symbol": "BTCUSDT"}),
        ("/fapi/v1/premiumIndex", {"symbol": "ETHUSDT"}),
    ]
    assert snapshots["BTCUSDT"].last_funding_rate == Decimal("0.0005")
    assert snapshots["ETHUSDT"].next_funding_time == 1_597_392_000_000


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


def test_fetch_klines_timeout_error_message_keeps_exception_detail(monkeypatch):
    import httpx
    import pytest

    from app.config.settings import Settings
    from app.data import binance
    from app.data.binance import BinanceDataError, fetch_klines

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, *args, **kwargs):
            raise httpx.ConnectTimeout("")

    async def fake_sleep(delay: float):
        return None

    monkeypatch.setattr(binance.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(binance.asyncio, "sleep", fake_sleep)

    with pytest.raises(BinanceDataError) as exc_info:
        asyncio.run(
            fetch_klines(
                "BTCUSDT",
                "1d",
                settings=Settings(binance_base_url="https://fapi.binance.com"),
            )
        )

    assert "ConnectTimeout" in str(exc_info.value)


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


def test_fetch_klines_filters_out_current_unclosed_kline(monkeypatch):
    from app.config.settings import Settings
    from app.data import binance
    from app.data.binance import fetch_klines

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                [0, "100", "101", "99", "100", "10", 899_999],
                [900_000, "101", "102", "100", "101", "10", 1_799_999],
            ]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(binance.httpx, "AsyncClient", FakeClient)

    rows = asyncio.run(
        fetch_klines(
            "BTCUSDT",
            "15m",
            settings=Settings(binance_base_url="https://fapi.binance.com"),
            now_ms=1_000_000,
        )
    )

    assert [row.open_time for row in rows] == [0]
