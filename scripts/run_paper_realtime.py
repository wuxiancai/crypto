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
from app.paper.strategy_adapter import RealtimeStrategyConfig
from app.paper.status import format_paper_status
from app.database.db import build_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run persistent Paper Trading on Binance WebSocket klines.")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--intervals", nargs="+", default=["15m", "1h", "4h", "1d"])
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
    parser.add_argument("--pullback-zone-atr-multiplier", default="1")
    parser.add_argument(
        "--require-pullback-close-beyond-fast-ma",
        action="store_true",
    )
    parser.add_argument("--enable-reversal-probe", action="store_true")
    parser.add_argument("--enable-layered-strategy", action="store_true")
    parser.add_argument("--trend-pullback-take-profit-mode", choices=["TRAILING", "FIXED"], default="TRAILING")
    return parser.parse_args()


def main() -> None:
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
                    pullback_zone_atr_multiplier=Decimal(args.pullback_zone_atr_multiplier),
                    require_pullback_close_beyond_fast_ma=args.require_pullback_close_beyond_fast_ma,
                    enable_reversal_probe=args.enable_reversal_probe,
                    enable_layered_strategy=args.enable_layered_strategy,
                ),
                event_session_factory=session_factory,
                kline_session_factory=session_factory,
            )
        )
    )
    print(format_paper_status(snapshot))


if __name__ == "__main__":
    main()
