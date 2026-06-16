from decimal import Decimal


def test_backtest_opens_and_closes_long_trade_with_costs():
    from app.backtest.engine import BacktestConfig, run_backtest
    from app.data.quality import Kline
    from app.strategy.pullback_strategy import TradeSignal

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

    def signal_fn(kline: Kline, has_position: bool) -> TradeSignal:
        if kline.open_time == 0 and not has_position:
            return TradeSignal(
                action="LONG_ENTRY",
                strategy_type="TREND_PULLBACK",
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
                risk_reward=Decimal("2"),
                reason=["test long"],
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

    result = run_backtest(
        klines=klines,
        signal_fn=signal_fn,
        config=BacktestConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            fee_rate=Decimal("0.001"),
            slippage_pct=Decimal("0.001"),
        ),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == "LONG"
    assert trade.exit_reason == "TAKE_PROFIT"
    assert trade.entry_price == Decimal("100.100")
    assert trade.exit_price == Decimal("109.890")
    assert trade.gross_pnl.quantize(Decimal("0.00001")) == Decimal("191.96078")
    assert trade.net_pnl.quantize(Decimal("0.00001")) == Decimal("187.84333")
    assert result.final_equity.quantize(Decimal("0.00001")) == Decimal("10187.84333")


def test_backtest_opens_and_stops_short_trade():
    from app.backtest.engine import BacktestConfig, run_backtest
    from app.data.quality import Kline
    from app.strategy.pullback_strategy import TradeSignal

    klines = [
        Kline(
            symbol="ETHUSDT",
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
            symbol="ETHUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("100"),
            high=Decimal("106"),
            low=Decimal("97"),
            close=Decimal("104"),
            volume=Decimal("10"),
        ),
    ]

    def signal_fn(kline: Kline, has_position: bool) -> TradeSignal:
        if kline.open_time == 0 and not has_position:
            return TradeSignal(
                action="SHORT_ENTRY",
                strategy_type="TREND_PULLBACK",
                entry_price=Decimal("100"),
                stop_loss=Decimal("105"),
                take_profit=Decimal("90"),
                risk_reward=Decimal("2"),
                reason=["test short"],
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

    result = run_backtest(
        klines=klines,
        signal_fn=signal_fn,
        config=BacktestConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
        ),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == "SHORT"
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.net_pnl == Decimal("-100")
    assert result.final_equity == Decimal("9900")


def test_backtest_executes_reversal_signal_and_reports_strategy_metrics():
    from app.backtest.engine import BacktestConfig, run_backtest
    from app.data.quality import Kline
    from app.strategy.reversal_strategy import ReversalSignal

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
            high=Decimal("106"),
            low=Decimal("98"),
            close=Decimal("105"),
            volume=Decimal("10"),
        ),
    ]

    def signal_fn(kline: Kline, has_position: bool) -> ReversalSignal:
        if kline.open_time == 0 and not has_position:
            return ReversalSignal(
                action="REVERSAL_LONG_ENTRY",
                strategy_type="REVERSAL_PROBE",
                signal_level="EARLY",
                score=Decimal("80"),
                risk_pct=Decimal("0.002"),
                max_standard_position_pct=Decimal("0.2"),
                reason=["test reversal"],
            )
        return ReversalSignal(
            action="WAIT",
            strategy_type="REVERSAL_PROBE",
            signal_level=None,
            score=Decimal("0"),
            risk_pct=None,
            max_standard_position_pct=None,
            reason=[],
        )

    result = run_backtest(
        klines=klines,
        signal_fn=signal_fn,
        config=BacktestConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            default_stop_distance_pct=Decimal("0.02"),
            default_take_profit_risk_reward=Decimal("2"),
        ),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == "LONG"
    assert trade.strategy_type == "REVERSAL_PROBE"
    assert trade.exit_reason == "TAKE_PROFIT"
    assert result.metrics.total_trades == 1
    assert result.metrics.by_strategy["REVERSAL_PROBE"].total_trades == 1
    assert result.metrics.by_strategy["REVERSAL_PROBE"].net_pnl == Decimal("100.00")
