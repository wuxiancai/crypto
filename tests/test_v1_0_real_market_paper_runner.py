import asyncio
from decimal import Decimal


def _kline(symbol: str, interval: str, index: int, close: str):
    from app.data.quality import INTERVAL_MS, Kline

    open_time = index * INTERVAL_MS[interval]
    price = Decimal(close)
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=open_time,
        close_time=open_time + INTERVAL_MS[interval] - 1,
        open=price,
        high=price + Decimal("2"),
        low=price - Decimal("2"),
        close=price,
        volume=Decimal("10"),
    )


def test_real_market_paper_runner_wires_source_to_persistent_stream(tmp_path):
    from app.data.quality import Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.paper.persistence import load_paper_snapshot

    state_path = tmp_path / "paper-state.json"

    async def source():
        yield Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=0,
            close_time=899_999,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
        )

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT", "ETHUSDT"),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0.0002"),
                taker_fee_rate=Decimal("0.0004"),
                slippage_pct=Decimal("0.0005"),
            ),
            source=source(),
        )
    )

    persisted = load_paper_snapshot(state_path)

    assert snapshot.equity == Decimal("10000")
    assert snapshot.open_position is None
    assert snapshot.rejected_signals == 0
    assert persisted == snapshot


def test_real_market_paper_runner_uses_injected_strategy_signal(tmp_path):
    from app.data.quality import Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.strategy.pullback_strategy import TradeSignal

    state_path = tmp_path / "paper-state.json"
    klines = [
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=0,
            close_time=899_999,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
        ),
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("100"),
            high=Decimal("111"),
            low=Decimal("99"),
            close=Decimal("110"),
            volume=Decimal("10"),
        ),
    ]

    async def source():
        for kline in klines:
            yield kline

    def signal_fn(kline: Kline, has_position: bool) -> TradeSignal:
        if kline.open_time == 0 and not has_position:
            return TradeSignal(
                action="LONG_ENTRY",
                strategy_type="TREND_PULLBACK",
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
                risk_reward=Decimal("2"),
                reason=["injected strategy"],
            )
        return TradeSignal(
            action="WAIT",
            strategy_type="TREND_PULLBACK",
            entry_price=None,
            stop_loss=None,
            take_profit=None,
            risk_reward=None,
            reason=[],
        )

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT",),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
            ),
            source=source(),
            signal_fn=signal_fn,
        )
    )

    assert snapshot.equity == Decimal("10100")
    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1


def test_real_market_paper_runner_uses_default_realtime_strategy(tmp_path):
    from app.data.quality import INTERVAL_MS, Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.paper.strategy_adapter import RealtimeStrategyConfig

    state_path = tmp_path / "paper-state.json"
    klines = [
        *[
            _kline("BTCUSDT", "4h", index, close)
            for index, close in enumerate(["100", "104", "108", "112", "116", "120"])
        ],
        *[
            _kline("BTCUSDT", "1h", index, close)
            for index, close in enumerate(["108", "112", "116", "120", "124", "128"])
        ],
        *[
            _kline("BTCUSDT", "15m", index, close)
            for index, close in enumerate(["120", "124", "128", "124", "126"])
        ],
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=5 * INTERVAL_MS["15m"],
            close_time=6 * INTERVAL_MS["15m"] - 1,
            open=Decimal("126"),
            high=Decimal("160"),
            low=Decimal("125"),
            close=Decimal("160"),
            volume=Decimal("10"),
        ),
    ]

    async def source():
        for kline in klines:
            yield kline

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT",),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                strategy_config=RealtimeStrategyConfig(
                    ema_fast_period=3,
                    ema_slow_period=5,
                    atr_period=3,
                    dmi_period=3,
                    swing_lookback=5,
                ),
            ),
            source=source(),
        )
    )

    assert snapshot.equity == Decimal("10100.00")
    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1
    assert snapshot.fills[0].strategy_type == "TREND_PULLBACK"


def test_real_market_paper_runner_uses_default_reversal_strategy(tmp_path):
    from app.data.quality import INTERVAL_MS, Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.paper.strategy_adapter import RealtimeStrategyConfig

    state_path = tmp_path / "paper-state.json"
    klines = [
        *[
            _kline("BTCUSDT", "4h", index, close)
            for index, close in enumerate(["120", "110", "100", "90", "80", "81"])
        ],
        *[
            _kline("BTCUSDT", "1h", index, close)
            for index, close in enumerate(["80", "84", "88", "92", "96", "100"])
        ],
        *[
            _kline("BTCUSDT", "15m", index, close)
            for index, close in enumerate(["90", "94", "98", "96", "97", "98"])
        ],
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=6 * INTERVAL_MS["15m"],
            close_time=7 * INTERVAL_MS["15m"] - 1,
            open=Decimal("98"),
            high=Decimal("120"),
            low=Decimal("97"),
            close=Decimal("120"),
            volume=Decimal("10"),
        ),
    ]

    async def source():
        for kline in klines:
            yield kline

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT",),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                strategy_config=RealtimeStrategyConfig(
                    ema_fast_period=3,
                    ema_slow_period=5,
                    atr_period=3,
                    dmi_period=3,
                    swing_lookback=5,
                ),
            ),
            source=source(),
        )
    )

    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1
    assert snapshot.fills[0].strategy_type == "REVERSAL_PROBE"
    assert snapshot.fills[0].net_pnl.quantize(Decimal("0.001")) == Decimal("40.000")
