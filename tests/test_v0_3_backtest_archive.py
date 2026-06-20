from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_archives_backtest_run_config_snapshot_and_trades():
    from app.backtest.engine import BacktestConfig, run_backtest
    from app.data.quality import Kline
    from app.database.models import BacktestRun, BacktestTradeRecord, Base, ConfigSnapshot
    from app.database.repositories import archive_backtest_result
    from app.strategy.pullback_strategy import TradeSignal

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

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
                reason=["archive"],
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

    with Session(engine) as session:
        run_id = archive_backtest_result(
            session=session,
            name="v0.3 archive test",
            config_name="unit",
            config_version="v1",
            config_payload={"risk_per_trade_pct": "0.01"},
            result=result,
        )

        saved_run = session.get(BacktestRun, run_id)
        saved_config = session.execute(select(ConfigSnapshot)).scalar_one()
        saved_trade = session.execute(select(BacktestTradeRecord)).scalar_one()

    assert saved_run is not None
    assert saved_run.name == "v0.3 archive test"
    assert saved_run.config_snapshot_id == saved_config.id
    assert saved_run.total_trades == 1
    assert saved_run.final_equity == Decimal("10200")
    assert saved_trade.backtest_run_id == run_id
    assert saved_trade.strategy_type == "TREND_PULLBACK"
    assert saved_trade.net_pnl == Decimal("200")


def test_clears_only_web_strategy_backtest_history():
    from app.database.models import BacktestRun, BacktestTradeRecord, Base, ConfigSnapshot
    from app.database.repositories import clear_strategy_backtest_history

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        strategy_config = ConfigSnapshot(
            name="strategy_backtest",
            version="v1",
            content_hash="strategy",
            content="{}",
        )
        other_config = ConfigSnapshot(
            name="unit",
            version="v1",
            content_hash="other",
            content="{}",
        )
        session.add_all([strategy_config, other_config])
        session.flush()
        strategy_run = BacktestRun(
            name="web_strategy_backtest",
            config_snapshot_id=strategy_config.id,
            initial_equity=Decimal("1000"),
            final_equity=Decimal("1010"),
            total_trades=1,
            wins=1,
            losses=0,
            net_pnl=Decimal("10"),
        )
        other_run = BacktestRun(
            name="v0.3 archive test",
            config_snapshot_id=other_config.id,
            initial_equity=Decimal("1000"),
            final_equity=Decimal("990"),
            total_trades=1,
            wins=0,
            losses=1,
            net_pnl=Decimal("-10"),
        )
        session.add_all([strategy_run, other_run])
        session.flush()
        for run in (strategy_run, other_run):
            session.add(
                BacktestTradeRecord(
                    backtest_run_id=run.id,
                    symbol="BTCUSDT",
                    side="LONG",
                    strategy_type="TREND_PULLBACK",
                    entry_time=1,
                    exit_time=2,
                    entry_price=Decimal("100"),
                    exit_price=Decimal("101"),
                    quantity=Decimal("1"),
                    gross_pnl=Decimal("1"),
                    fees=Decimal("0"),
                    funding_fee=Decimal("0"),
                    net_pnl=Decimal("1"),
                    exit_reason="TAKE_PROFIT",
                )
            )
        session.commit()

        counts = clear_strategy_backtest_history(session)

        remaining_runs = session.execute(select(BacktestRun)).scalars().all()
        remaining_trades = session.execute(select(BacktestTradeRecord)).scalars().all()
        remaining_configs = session.execute(select(ConfigSnapshot)).scalars().all()

    assert counts == {"runs": 1, "trades": 1, "config_snapshots": 1}
    assert [run.name for run in remaining_runs] == ["v0.3 archive test"]
    assert len(remaining_trades) == 1
    assert [config.name for config in remaining_configs] == ["unit"]
