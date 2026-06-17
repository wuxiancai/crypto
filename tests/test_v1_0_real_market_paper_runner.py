import asyncio
from decimal import Decimal


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
