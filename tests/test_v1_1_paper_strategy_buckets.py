from decimal import Decimal


def _kline(symbol: str = "BTCUSDT", open_time: int = 0):
    from app.data.quality import Kline

    return Kline(
        symbol=symbol,
        interval="15m",
        open_time=open_time,
        close_time=open_time + 899_999,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("10"),
    )


def _signal(action: str, strategy_type: str, stop_loss: str, take_profit: str, bucket: str):
    from app.strategy.signal_router import StrategySignal

    return StrategySignal(
        action=action,
        strategy_type=strategy_type,
        bucket=bucket,
        entry_price=Decimal("100"),
        stop_loss=Decimal(stop_loss),
        take_profit=Decimal(take_profit),
        risk_reward=Decimal("2"),
        reason=[strategy_type],
    )


def test_paper_trading_allows_core_short_and_4h_long_hedge_to_coexist():
    from app.paper.trading import PaperConfig, PaperTradingEngine

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

    short_core = engine.on_signal(
        _kline(),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "105", "90", "DAY_CORE"),
    )
    long_hedge = engine.on_signal(
        _kline(open_time=900_000),
        _signal("LONG_ENTRY", "LONG_4H_HEDGE", "95", "110", "FOUR_HOUR_HEDGE"),
    )

    assert short_core is not None
    assert long_hedge is not None
    snapshot = engine.snapshot()
    assert snapshot.open_position == short_core
    assert [position.strategy_type for position in snapshot.open_positions] == [
        "SHORT_DAY_CORE",
        "LONG_4H_HEDGE",
    ]


def test_paper_trading_blocks_duplicate_bucket_position():
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
        )
    )

    assert engine.on_signal(
        _kline(),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "105", "90", "DAY_CORE"),
    ) is not None
    assert engine.on_signal(
        _kline(open_time=900_000),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "106", "88", "DAY_CORE"),
    ) is None

    snapshot = engine.snapshot()
    assert len(snapshot.open_positions) == 1
    assert snapshot.rejected_signals == 1

