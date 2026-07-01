from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
from app.paper.strategy_adapter import RealtimeStrategyConfig
from app.paper.status import format_paper_status
from app.database.db import build_session_factory


class _TimestampedLineWriter:
    def __init__(
        self,
        wrapped: TextIO,
        now: Callable[[], str] | None = None,
    ) -> None:
        self._wrapped = wrapped
        self._now = now or _current_log_time
        self._line_start = True

    def write(self, text: str) -> int:
        if not text:
            return 0
        for chunk in text.splitlines(keepends=True):
            if self._line_start and chunk not in {"\n", "\r\n"}:
                self._wrapped.write(f"{self._now()} ")
            self._wrapped.write(chunk)
            self._line_start = chunk.endswith("\n")
        return len(text)

    def flush(self) -> None:
        self._wrapped.flush()

    def isatty(self) -> bool:
        return self._wrapped.isatty()

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)


def _current_log_time() -> str:
    utc_plus_8 = timezone(timedelta(hours=8))
    return datetime.now(tz=utc_plus_8).strftime("%Y-%m-%d %H:%M:%S")


def _enable_timestamped_stdio() -> None:
    sys.stdout = _TimestampedLineWriter(sys.stdout)
    sys.stderr = _TimestampedLineWriter(sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run persistent Paper Trading on Binance WebSocket klines.")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--intervals", nargs="+", default=["1w", "1d", "4h"])
    parser.add_argument("--websocket-base-url", default="wss://fstream.binance.com/market")
    parser.add_argument("--state-path", type=Path, default=Path("runtime/paper-state.json"))
    parser.add_argument("--initial-equity", default="1000")
    parser.add_argument("--risk-per-trade-pct", default="0.005")
    parser.add_argument("--maker-fee-rate", default="0.0002")
    parser.add_argument("--taker-fee-rate", default="0.0005")
    parser.add_argument("--slippage-pct", default="0.0005")
    parser.add_argument("--leverage", default="10")
    parser.add_argument("--funding-rate", default="0")
    parser.add_argument("--fast-ma-type", choices=["EMA", "MA"], default="EMA")
    parser.add_argument("--slow-ma-type", choices=["EMA", "MA"], default="MA")
    parser.add_argument("--ema-fast-period", type=int, default=15)
    parser.add_argument("--ema-slow-period", type=int, default=60)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--dmi-period", type=int, default=12)
    parser.add_argument("--swing-lookback", type=int, default=20)
    parser.add_argument("--max-fee-to-risk-ratio", default="0.25")
    parser.add_argument("--trend-pullback-take-profit-mode", choices=["TRAILING", "FIXED"], default="TRAILING")
    return parser.parse_args()


def main() -> None:
    _enable_timestamped_stdio()
    args = parse_args()
    session_factory = build_session_factory()
    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=tuple(args.symbols),
                intervals=tuple(args.intervals),
                websocket_base_url=args.websocket_base_url,
                state_path=args.state_path,
                initial_equity=Decimal(args.initial_equity),
                risk_per_trade_pct=Decimal(args.risk_per_trade_pct),
                maker_fee_rate=Decimal(args.maker_fee_rate),
                taker_fee_rate=Decimal(args.taker_fee_rate),
                slippage_pct=Decimal(args.slippage_pct),
                leverage=Decimal(args.leverage),
                funding_rate=Decimal(args.funding_rate),
                max_fee_to_risk_ratio=Decimal(args.max_fee_to_risk_ratio),
                trend_pullback_take_profit_mode=args.trend_pullback_take_profit_mode,
                strategy_config=RealtimeStrategyConfig(
                    fast_ma_type=args.fast_ma_type,
                    slow_ma_type=args.slow_ma_type,
                    ema_fast_period=args.ema_fast_period,
                    ema_slow_period=args.ema_slow_period,
                    atr_period=args.atr_period,
                    dmi_period=args.dmi_period,
                    swing_lookback=args.swing_lookback,
                    strategy_kernel="WEEKLY_DAILY_H4_V1",
                ),
                event_session_factory=session_factory,
                kline_session_factory=session_factory,
            )
        )
    )
    print(format_paper_status(snapshot))


if __name__ == "__main__":
    main()
