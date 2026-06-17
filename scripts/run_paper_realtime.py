from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
from app.paper.status import format_paper_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run persistent Paper Trading on Binance WebSocket klines.")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--websocket-base-url", default="wss://fstream.binance.com")
    parser.add_argument("--state-path", type=Path, default=Path("runtime/paper-state.json"))
    parser.add_argument("--initial-equity", default="10000")
    parser.add_argument("--risk-per-trade-pct", default="0.005")
    parser.add_argument("--maker-fee-rate", default="0.0002")
    parser.add_argument("--taker-fee-rate", default="0.0004")
    parser.add_argument("--slippage-pct", default="0.0005")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=tuple(args.symbols),
                interval=args.interval,
                websocket_base_url=args.websocket_base_url,
                state_path=args.state_path,
                initial_equity=Decimal(args.initial_equity),
                risk_per_trade_pct=Decimal(args.risk_per_trade_pct),
                maker_fee_rate=Decimal(args.maker_fee_rate),
                taker_fee_rate=Decimal(args.taker_fee_rate),
                slippage_pct=Decimal(args.slippage_pct),
            )
        )
    )
    print(format_paper_status(snapshot))


if __name__ == "__main__":
    main()
