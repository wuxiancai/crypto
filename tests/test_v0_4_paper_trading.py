from decimal import Decimal


def test_paper_trading_opens_and_closes_long_position():
    from app.data.quality import Kline
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.pullback_strategy import TradeSignal

    engine = PaperTradingEngine(
        config=PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
        )
    )
    signal = TradeSignal(
        action="LONG_ENTRY",
        strategy_type="TREND_PULLBACK",
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        risk_reward=Decimal("2"),
        reason=["paper long"],
    )

    opened = engine.on_signal(
        kline=Kline(
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
        signal=signal,
    )

    assert opened is not None
    assert engine.snapshot().open_position is not None
    assert engine.snapshot().equity == Decimal("10000")

    fill = engine.on_kline(
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
        )
    )

    assert fill is not None
    assert fill.exit_reason == "TAKE_PROFIT"
    assert fill.net_pnl == Decimal("200")
    assert engine.snapshot().equity == Decimal("10200")
    assert engine.snapshot().open_position is None


def test_paper_trading_blocks_second_position_until_first_closes():
    from app.data.quality import Kline
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.pullback_strategy import TradeSignal

    engine = PaperTradingEngine(
        config=PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
        )
    )
    kline = Kline(
        symbol="ETHUSDT",
        interval="15m",
        open_time=0,
        close_time=899_999,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("10"),
    )
    signal = TradeSignal(
        action="SHORT_ENTRY",
        strategy_type="TREND_PULLBACK",
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        take_profit=Decimal("90"),
        risk_reward=Decimal("2"),
        reason=["paper short"],
    )

    assert engine.on_signal(kline=kline, signal=signal) is not None
    assert engine.on_signal(kline=kline, signal=signal) is None
    assert engine.snapshot().rejected_signals == 1
