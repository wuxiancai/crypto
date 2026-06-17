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
                interval="15m",
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
