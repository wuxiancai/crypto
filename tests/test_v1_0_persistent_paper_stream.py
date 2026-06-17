import asyncio
from decimal import Decimal


def test_persistent_paper_stream_restores_state_and_saves_after_each_kline(tmp_path):
    from app.data.quality import Kline
    from app.paper.persistence import load_paper_snapshot, save_paper_snapshot
    from app.paper.stream import run_persistent_paper_kline_stream
    from app.paper.trading import PaperConfig, PaperPosition, PaperSnapshot
    from app.strategy.pullback_strategy import TradeSignal

    state_path = tmp_path / "paper-state.json"
    save_paper_snapshot(
        PaperSnapshot(
            equity=Decimal("10000"),
            open_position=PaperPosition(
                symbol="BTCUSDT",
                side="LONG",
                strategy_type="TREND_PULLBACK",
                entry_time=0,
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
                quantity=Decimal("20"),
                entry_fee=Decimal("0"),
            ),
            fills=[],
            rejected_signals=0,
        ),
        state_path,
    )

    async def source():
        yield Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("100"),
            high=Decimal("111"),
            low=Decimal("99"),
            close=Decimal("110"),
            volume=Decimal("10"),
        )

    def signal_fn(kline: Kline, has_position: bool) -> TradeSignal:
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
        run_persistent_paper_kline_stream(
            config=PaperConfig(
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.01"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
            ),
            source=source(),
            signal_fn=signal_fn,
            state_path=state_path,
        )
    )

    persisted = load_paper_snapshot(state_path)

    assert snapshot.equity == Decimal("10200")
    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1
    assert persisted == snapshot
