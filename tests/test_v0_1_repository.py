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
        inserted = upsert_klines(session, [row])
        unchanged = upsert_klines(session, [row])
        updated = upsert_klines(session, [row.model_copy(update={"close": Decimal("106")})])

        assert inserted.inserted == 1
        assert inserted.updated == 0
        assert inserted.unchanged == 0
        assert unchanged.inserted == 0
        assert unchanged.updated == 0
        assert unchanged.unchanged == 1
        assert unchanged.written == 0
        assert updated.inserted == 0
        assert updated.updated == 1
        assert updated.unchanged == 0
        assert updated == 1

        saved = session.execute(select(KlineRecord)).scalar_one()
        assert saved.close == Decimal("106")
        assert session.query(KlineRecord).count() == 1

