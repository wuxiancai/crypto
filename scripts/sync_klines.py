from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config.settings import Settings
from app.data.binance import BinanceDataError, fetch_klines
from app.data.quality import validate_kline_sequence
from app.database.db import build_session_factory
from app.database.repositories import upsert_klines


async def sync_klines(symbols: Sequence[str], intervals: Sequence[str], limit: int, dry_run: bool) -> None:
    settings = Settings()
    session_factory = None if dry_run else build_session_factory(settings)

    for symbol in symbols:
        for interval in intervals:
            try:
                rows = await fetch_klines(symbol=symbol, interval=interval, limit=limit, settings=settings)
            except BinanceDataError as exc:
                raise RuntimeError(f"failed to fetch {symbol} {interval}: {exc}") from exc
            errors = validate_kline_sequence(rows)
            if errors:
                joined = "\n".join(errors[:10])
                raise RuntimeError(f"{symbol} {interval} failed quality checks:\n{joined}")
            if dry_run:
                print(f"DRY-RUN {symbol} {interval}: fetched {len(rows)} closed klines")
                continue
            assert session_factory is not None
            with session_factory() as session:
                written = upsert_klines(session, rows)
            print(f"WROTE {symbol} {interval}: {written} klines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Binance USDT-M klines and optionally upsert them.")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--intervals", nargs="+", default=["15m", "1h", "4h"])
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--write", action="store_true", help="Write to DATABASE_URL instead of dry-run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(sync_klines(args.symbols, args.intervals, args.limit, dry_run=not args.write))


if __name__ == "__main__":
    main()
