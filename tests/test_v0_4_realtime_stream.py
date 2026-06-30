import asyncio
from decimal import Decimal


def test_paper_stream_consumes_async_klines_and_updates_engine():
    from app.data.quality import Kline
    from app.paper.stream import run_paper_kline_stream
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal as TradeSignal

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
                reason=["stream long"],
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

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
            )
        )

    snapshot = asyncio.run(run_paper_kline_stream(engine=engine, source=source(), signal_fn=signal_fn))

    assert snapshot.equity == Decimal("10200")
    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1
