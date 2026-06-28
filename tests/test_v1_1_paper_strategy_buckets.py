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


def test_paper_trading_rejects_duplicate_day_core_instead_of_implicitly_converting_to_addon():
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0"),
        )
    )

    assert engine.on_signal(
        _kline(),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "105", "90", "DAY_CORE"),
    ) is not None
    duplicate_core = engine.on_signal(
        _kline(open_time=900_000),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "106", "88", "DAY_CORE"),
    )

    snapshot = engine.snapshot()
    assert duplicate_core is None
    assert len(snapshot.open_positions) == 1
    assert snapshot.open_positions[0].strategy_type == "SHORT_DAY_CORE"
    assert snapshot.rejected_signals == 1


def test_paper_trading_blocks_duplicate_addon_bucket_position():
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0"),
        )
    )

    engine.on_signal(_kline(), _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "105", "90", "DAY_CORE"))
    engine.on_signal(_kline(open_time=900_000), _signal("SHORT_ENTRY", "SHORT_4H_1H_ADDON", "106", "88", "FOUR_HOUR_ADDON"))
    assert engine.on_signal(
        _kline(open_time=1_800_000),
        _signal("SHORT_ENTRY", "SHORT_4H_1H_ADDON", "107", "86", "FOUR_HOUR_ADDON"),
    ) is None

    snapshot = engine.snapshot()
    assert len(snapshot.open_positions) == 2
    assert snapshot.rejected_signals == 1


def test_paper_trading_exits_day_core_on_daily_regime_reversal_without_closing_hedge():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0"),
        )
    )

    engine.on_signal(
        _kline(),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "105", "90", "DAY_CORE"),
    )
    engine.on_signal(
        _kline(open_time=900_000),
        _signal("LONG_ENTRY", "LONG_4H_HEDGE", "95", "110", "FOUR_HOUR_HEDGE"),
    )

    fill = engine.on_signal(
        _kline(open_time=1_800_000),
        StrategySignal(
            action="EXIT_DAY_CORE_REVERSAL",
            strategy_type="LONG_DAY_CORE",
            bucket="DAY_CORE",
            reason=["daily regime reversed from SHORT to LONG"],
        ),
    )

    assert fill is not None
    assert fill.strategy_type == "SHORT_DAY_CORE"
    assert fill.bucket == "DAY_CORE"
    assert fill.exit_reason == "DAILY_REGIME_REVERSAL"
    snapshot = engine.snapshot()
    assert len(snapshot.open_positions) == 1
    assert snapshot.open_positions[0].strategy_type == "LONG_4H_HEDGE"


def test_paper_trading_caps_single_position_notional_below_total_leverage():
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.5"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            leverage=Decimal("10"),
            max_single_position_notional_leverage=Decimal("3"),
            max_fee_to_risk_ratio=Decimal("0"),
            max_total_planned_risk_pct=None,
        )
    )

    position = engine.on_signal(
        _kline(),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "101", "98", "DAY_CORE"),
    )

    assert position is not None
    assert position.entry_price * position.quantity == Decimal("30000")


def test_paper_trading_blocks_new_position_when_portfolio_risk_limit_is_exceeded():
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0"),
            max_total_planned_risk_pct=Decimal("0.011"),
        )
    )

    assert engine.on_signal(_kline(), _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "105", "90", "DAY_CORE")) is not None
    assert engine.on_signal(
        _kline(open_time=900_000),
        _signal("LONG_ENTRY", "LONG_4H_HEDGE", "95", "110", "FOUR_HOUR_HEDGE"),
    ) is None

    snapshot = engine.snapshot()
    assert len(snapshot.open_positions) == 1
    assert snapshot.rejected_signals == 1


def test_paper_trading_rejects_explicit_zero_risk_signal():
    from app.paper.trading import PaperConfig, PaperTradingEngine
    from app.strategy.signal_router import StrategySignal

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0"),
        )
    )

    position = engine.on_signal(
        _kline(),
        StrategySignal(
            action="LONG_ENTRY",
            strategy_type="LONG_DAY_CORE",
            bucket="DAY_CORE",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            risk_pct=Decimal("0"),
            reason=["blocked by upstream risk"],
        ),
    )

    snapshot = engine.snapshot()
    assert position is None
    assert snapshot.open_positions == []
    assert snapshot.rejected_signals == 1


def test_paper_trading_blocks_entries_when_kill_switch_is_active():
    from app.execution.kill_switch import activate_kill_switch
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0"),
            kill_switch=activate_kill_switch("test", "max drawdown", close_positions=False),
        )
    )

    assert engine.on_signal(
        _kline(),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "105", "90", "DAY_CORE"),
    ) is None

    snapshot = engine.snapshot()
    assert snapshot.open_positions == []
    assert snapshot.rejected_signals == 1


def test_paper_trading_blocks_entries_when_max_drawdown_is_reached():
    from app.paper.trading import PaperConfig, PaperTradingEngine, PaperSnapshot

    config = PaperConfig(
        initial_equity=Decimal("10000"),
        risk_per_trade_pct=Decimal("0.01"),
        maker_fee_rate=Decimal("0"),
        taker_fee_rate=Decimal("0"),
        slippage_pct=Decimal("0"),
        max_fee_to_risk_ratio=Decimal("0"),
        max_drawdown_pct=Decimal("0.05"),
    )
    engine = PaperTradingEngine.from_snapshot(
        config,
        PaperSnapshot(
            equity=Decimal("9499"),
            open_position=None,
            fills=[],
            rejected_signals=0,
        ),
    )

    assert engine.on_signal(
        _kline(),
        _signal("LONG_ENTRY", "LONG_DAY_CORE", "95", "110", "DAY_CORE"),
    ) is None

    assert engine.snapshot().rejected_signals == 1


def test_paper_trading_blocks_entry_when_stop_is_too_close_to_liquidation_price():
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0"),
            liquidation_buffer_pct=Decimal("0.01"),
        )
    )

    assert engine.on_signal(
        _kline(),
        _signal("LONG_ENTRY", "LONG_DAY_CORE", "90.40", "110", "DAY_CORE"),
    ) is None

    assert engine.snapshot().rejected_signals == 1


def test_paper_trading_liquidates_position_before_stop_when_price_crosses_liquidation():
    from app.data.quality import Kline
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            leverage=Decimal("10"),
            max_fee_to_risk_ratio=Decimal("0"),
        )
    )
    engine.on_signal(
        _kline(),
        _signal("LONG_ENTRY", "LONG_DAY_CORE", "95", "110", "DAY_CORE"),
    )

    fills = engine.on_kline_all(
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("89"),
            high=Decimal("91"),
            low=Decimal("88"),
            close=Decimal("90"),
            volume=Decimal("10"),
        )
    )

    assert fills[0].exit_reason == "LIQUIDATION"
    assert fills[0].exit_price == Decimal("90")


def test_paper_trading_exits_opposite_day_core_when_new_daily_core_signal_arrives():
    from app.paper.trading import PaperConfig, PaperTradingEngine

    engine = PaperTradingEngine(
        PaperConfig(
            initial_equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
            max_fee_to_risk_ratio=Decimal("0"),
        )
    )

    engine.on_signal(
        _kline(),
        _signal("SHORT_ENTRY", "SHORT_DAY_CORE", "105", "90", "DAY_CORE"),
    )

    fill = engine.on_signal(
        _kline(open_time=900_000),
        _signal("LONG_ENTRY", "LONG_DAY_CORE", "95", "115", "DAY_CORE"),
    )

    assert fill is not None
    assert fill.strategy_type == "SHORT_DAY_CORE"
    assert fill.exit_reason == "DAILY_REGIME_REVERSAL"
    snapshot = engine.snapshot()
    assert snapshot.open_positions == []
    assert snapshot.rejected_signals == 0
