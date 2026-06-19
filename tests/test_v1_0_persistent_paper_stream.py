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


def test_persistent_paper_stream_does_not_reenter_on_same_kline_after_exit(tmp_path):
    from app.data.quality import Kline
    from app.paper.persistence import save_paper_snapshot
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
            action="LONG_ENTRY",
            strategy_type="TREND_PULLBACK",
            entry_price=Decimal("110"),
            stop_loss=Decimal("100"),
            take_profit=Decimal("130"),
            risk_reward=Decimal("2"),
            reason=["same candle reentry"],
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

    assert len(snapshot.fills) == 1
    assert snapshot.open_position is None
    assert snapshot.signal_evaluations[-1].reason == ("position closed on current kline",)


def test_persistent_paper_stream_records_wait_signal_reason(tmp_path):
    from app.data.quality import Kline
    from app.paper.persistence import load_paper_snapshot
    from app.paper.stream import run_persistent_paper_kline_stream
    from app.paper.trading import PaperConfig
    from app.strategy.pullback_strategy import TradeSignal

    state_path = tmp_path / "paper-state.json"

    async def source():
        yield Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
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
            reason=["price not in ema50 pullback zone"],
        )

    snapshot = asyncio.run(
        run_persistent_paper_kline_stream(
            config=PaperConfig(
                initial_equity=Decimal("1000"),
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

    assert persisted == snapshot
    assert snapshot.signal_evaluations[-1].action == "WAIT"
    assert snapshot.signal_evaluations[-1].symbol == "BTCUSDT"
    assert snapshot.signal_evaluations[-1].interval == "15m"
    assert snapshot.signal_evaluations[-1].reason == ("price not in ema50 pullback zone",)


def test_persistent_paper_stream_keeps_latest_strategy_output_per_symbol_interval(tmp_path):
    from app.data.quality import Kline
    from app.paper.persistence import load_paper_snapshot
    from app.paper.stream import run_persistent_paper_kline_stream
    from app.paper.trading import PaperConfig
    from app.strategy.signal_router import StrategySignal

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
            interval="5m",
            open_time=900_000,
            close_time=1_199_999,
            open=Decimal("101"),
            high=Decimal("102"),
            low=Decimal("100"),
            close=Decimal("101"),
            volume=Decimal("10"),
        ),
        Kline(
            symbol="BTCUSDT",
            interval="5m",
            open_time=1_200_000,
            close_time=1_499_999,
            open=Decimal("102"),
            high=Decimal("103"),
            low=Decimal("101"),
            close=Decimal("102"),
            volume=Decimal("10"),
        ),
    ]

    async def source():
        for kline in klines:
            yield kline

    def signal_fn(kline: Kline, has_position: bool) -> StrategySignal:
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=[f"latest {kline.interval}"],
        )

    snapshot = asyncio.run(
        run_persistent_paper_kline_stream(
            config=PaperConfig(
                initial_equity=Decimal("1000"),
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

    assert persisted == snapshot
    assert [(item.symbol, item.interval) for item in snapshot.signal_evaluations] == [
        ("BTCUSDT", "15m"),
        ("BTCUSDT", "5m"),
    ]
    assert snapshot.signal_evaluations[-1].reason == ("latest 5m",)
