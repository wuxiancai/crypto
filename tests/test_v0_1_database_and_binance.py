from decimal import Decimal


def test_database_metadata_contains_v0_1_tables():
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

