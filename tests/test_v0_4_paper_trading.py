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
            trend_pullback_take_profit_mode="FIXED",
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


def test_trend_pullback_moves_take_profit_by_two_r_steps_and_exits_on_rebound():
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
        signal=TradeSignal(
            action="SHORT_ENTRY",
            strategy_type="TREND_PULLBACK",
            entry_price=Decimal("100"),
            stop_loss=Decimal("105"),
            take_profit=Decimal("90"),
            risk_reward=Decimal("2"),
            reason=["paper short"],
        ),
    )

    assert opened is not None
    activation_fill = engine.on_kline(
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("89"),
            close=Decimal("90"),
            volume=Decimal("10"),
        )
    )

    assert activation_fill is None
    active_position = engine.snapshot().open_position
    assert active_position is not None
    assert active_position.trailing_active is True
    assert active_position.stop_loss == Decimal("90")

    continuation_fill = engine.on_kline(
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=1_800_000,
            close_time=2_699_999,
            open=Decimal("89"),
            high=Decimal("89"),
            low=Decimal("80"),
            close=Decimal("82"),
            volume=Decimal("10"),
        )
    )

    assert continuation_fill is None
    trailed_position = engine.snapshot().open_position
    assert trailed_position is not None
    assert trailed_position.stop_loss == Decimal("80")

    exit_fill = engine.on_kline(
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=2_700_000,
            close_time=3_599_999,
            open=Decimal("79"),
            high=Decimal("80"),
            low=Decimal("78"),
            close=Decimal("79"),
            volume=Decimal("10"),
        )
    )

    assert exit_fill is not None
    assert exit_fill.exit_reason == "TRAILING_TAKE_PROFIT"
    assert exit_fill.exit_price == Decimal("80")
    assert exit_fill.net_pnl == Decimal("400")
    assert engine.snapshot().open_position is None


def test_long_trend_pullback_moves_take_profit_by_two_r_steps_and_exits_on_pullback():
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
        signal=TradeSignal(
            action="LONG_ENTRY",
            strategy_type="TREND_PULLBACK",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            risk_reward=Decimal("2"),
            reason=["paper long"],
        ),
    )

    assert opened is not None
    assert engine.on_kline(
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
    ) is None
    active_position = engine.snapshot().open_position
    assert active_position is not None
    assert active_position.stop_loss == Decimal("110")

    assert engine.on_kline(
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=1_800_000,
            close_time=2_699_999,
            open=Decimal("111"),
            high=Decimal("120"),
            low=Decimal("111"),
            close=Decimal("118"),
            volume=Decimal("10"),
        )
    ) is None
    trailed_position = engine.snapshot().open_position
    assert trailed_position is not None
    assert trailed_position.stop_loss == Decimal("120")

    exit_fill = engine.on_kline(
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=2_700_000,
            close_time=3_599_999,
            open=Decimal("121"),
            high=Decimal("122"),
            low=Decimal("120"),
            close=Decimal("121"),
            volume=Decimal("10"),
        )
    )

    assert exit_fill is not None
    assert exit_fill.exit_reason == "TRAILING_TAKE_PROFIT"
    assert exit_fill.exit_price == Decimal("120")
    assert exit_fill.net_pnl == Decimal("400")
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


def test_paper_trading_ignores_exit_klines_from_other_symbols_and_timeframes():
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
            trend_pullback_take_profit_mode="FIXED",
        )
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
        signal=TradeSignal(
            action="LONG_ENTRY",
            strategy_type="TREND_PULLBACK",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            risk_reward=Decimal("2"),
            reason=["paper long"],
        ),
    )

    assert opened is not None
    assert engine.on_kline(
        Kline(
            symbol="ETHUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("100"),
            high=Decimal("200"),
            low=Decimal("50"),
            close=Decimal("150"),
            volume=Decimal("10"),
        )
    ) is None
    assert engine.on_kline(
        Kline(
            symbol="BTCUSDT",
            interval="1h",
            open_time=900_000,
            close_time=4_499_999,
            open=Decimal("100"),
            high=Decimal("200"),
            low=Decimal("50"),
            close=Decimal("150"),
            volume=Decimal("10"),
        )
    ) is None
    assert engine.snapshot().open_position is not None

    fill = engine.on_kline(
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=1_800_000,
            close_time=2_699_999,
            open=Decimal("100"),
            high=Decimal("111"),
            low=Decimal("99"),
            close=Decimal("110"),
            volume=Decimal("10"),
        )
    )

    assert fill is not None
    assert fill.exit_reason == "TAKE_PROFIT"


def test_paper_trading_accepts_reversal_signal_with_signal_risk_cap():
    from app.data.quality import Kline
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.reversal_strategy import ReversalSignal

    engine = PaperTradingEngine(
        config=PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            default_stop_distance_pct=Decimal("0.02"),
            default_take_profit_risk_reward=Decimal("2"),
        )
    )
    kline = Kline(
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

    position = engine.on_signal(
        kline=kline,
        signal=ReversalSignal(
            action="REVERSAL_LONG_ENTRY",
            strategy_type="REVERSAL_PROBE",
            signal_level="EARLY",
            score=Decimal("80"),
            risk_pct=Decimal("0.002"),
            max_standard_position_pct=Decimal("0.2"),
            reason=["paper reversal"],
        ),
    )

    assert position is not None
    assert position.side == "LONG"
    assert position.strategy_type == "REVERSAL_PROBE"
    assert position.entry_price == Decimal("100")
    assert position.stop_loss == Decimal("98.00")
    assert position.take_profit == Decimal("104.00")
    assert position.quantity == Decimal("10")


def test_paper_trading_defaults_to_perpetual_contract_costs_and_10x_leverage():
    from app.data.quality import Kline
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.pullback_strategy import TradeSignal

    config = PaperConfig(
        initial_equity=Decimal("1000"),
        risk_per_trade_pct=Decimal("1"),
        slippage_pct=Decimal("0"),
    )
    assert config.maker_fee_rate == Decimal("0.0002")
    assert config.taker_fee_rate == Decimal("0.0005")
    assert config.leverage == Decimal("10")
    assert config.funding_interval_ms == 8 * 60 * 60 * 1000

    engine = PaperTradingEngine(config=config)
    opened = engine.on_signal(
        kline=Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=0,
            close_time=899_999,
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=Decimal("10"),
        ),
        signal=TradeSignal(
            action="LONG_ENTRY",
            strategy_type="TREND_PULLBACK",
            entry_price=Decimal("100"),
            stop_loss=Decimal("99"),
            take_profit=Decimal("110"),
            risk_reward=Decimal("10"),
            reason=["leverage cap"],
        ),
    )

    assert opened is not None
    assert opened.quantity == Decimal("100")
    assert opened.entry_fee == Decimal("5.0000")


def test_paper_trading_rejects_entry_when_estimated_fees_are_too_high_for_planned_risk():
    from app.data.quality import Kline
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.pullback_strategy import TradeSignal

    engine = PaperTradingEngine(
        config=PaperConfig(
            initial_equity=Decimal("1000"),
            risk_per_trade_pct=Decimal("0.005"),
            maker_fee_rate=Decimal("0.0002"),
            taker_fee_rate=Decimal("0.0005"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0.4"),
        )
    )
    kline = Kline(
        symbol="BTCUSDT",
        interval="15m",
        open_time=0,
        close_time=899_999,
        open=Decimal("100000"),
        high=Decimal("100000"),
        low=Decimal("100000"),
        close=Decimal("100000"),
        volume=Decimal("10"),
    )

    opened = engine.on_signal(
        kline=kline,
        signal=TradeSignal(
            action="LONG_ENTRY",
            strategy_type="TREND_PULLBACK",
            entry_price=Decimal("100000"),
            stop_loss=Decimal("99950"),
            take_profit=Decimal("100100"),
            risk_reward=Decimal("2"),
            reason=["too tight after fees"],
        ),
    )

    assert opened is None
    snapshot = engine.snapshot()
    assert snapshot.open_position is None
    assert snapshot.rejected_signals == 1


def test_paper_trading_applies_funding_every_eight_hours():
    from app.data.quality import Kline
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.pullback_strategy import TradeSignal

    engine = PaperTradingEngine(
        config=PaperConfig(
            initial_equity=Decimal("1000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            funding_rate=Decimal("0.0001"),
            trend_pullback_take_profit_mode="FIXED",
        )
    )
    position = engine.on_signal(
        kline=Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=0,
            close_time=899_999,
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=Decimal("10"),
        ),
        signal=TradeSignal(
            action="LONG_ENTRY",
            strategy_type="TREND_PULLBACK",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            risk_reward=Decimal("2"),
            reason=["funding"],
        ),
    )

    assert position is not None
    fill = engine.on_kline(
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=8 * 60 * 60 * 1000,
            close_time=8 * 60 * 60 * 1000 + 899_999,
            open=Decimal("100"),
            high=Decimal("111"),
            low=Decimal("100"),
            close=Decimal("110"),
            volume=Decimal("10"),
        )
    )

    assert fill is not None
    assert fill.funding_fee == Decimal("0.020000")
    assert fill.net_pnl == Decimal("19.980000")
