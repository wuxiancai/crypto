from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.quality import Kline
from app.database.models import KlineRecord


def upsert_klines(session: Session, rows: list[Kline]) -> int:
    written = 0
    for row in rows:
        existing = session.execute(
            select(KlineRecord).where(
                KlineRecord.symbol == row.symbol,
                KlineRecord.interval == row.interval,
                KlineRecord.open_time == row.open_time,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(_to_record(row))
        else:
            existing.close_time = row.close_time
            existing.open = row.open
            existing.high = row.high
            existing.low = row.low
            existing.close = row.close
            existing.volume = row.volume
            existing.is_closed = row.is_closed
        written += 1
    session.commit()
    return written


def _to_record(row: Kline) -> KlineRecord:
    return KlineRecord(
        symbol=row.symbol,
        interval=row.interval,
        open_time=row.open_time,
        close_time=row.close_time,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        volume=row.volume,
        is_closed=row.is_closed,
    )

