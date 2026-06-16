from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_upserts_klines_by_symbol_interval_open_time():
    from app.data.quality import Kline
    from app.database.models import Base, KlineRecord
    from app.database.repositories import upsert_klines

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    row = Kline(
        symbol="BTCUSDT",
        interval="15m",
        open_time=0,
        close_time=899_999,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("95"),
        close=Decimal("105"),
        volume=Decimal("10"),
    )

    with Session(engine) as session:
        assert upsert_klines(session, [row]) == 1
        assert upsert_klines(session, [row.model_copy(update={"close": Decimal("106")})]) == 1

        saved = session.execute(select(KlineRecord)).scalar_one()
        assert saved.close == Decimal("106")
        assert session.query(KlineRecord).count() == 1

