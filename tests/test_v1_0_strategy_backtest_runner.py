import asyncio
import json
from decimal import Decimal


def _kline(
    symbol: str,
    interval: str,
    index: int,
    close: str,
    open_price: str | None = None,
    high: str | None = None,
    low: str | None = None,
):
    from app.data.quality import INTERVAL_MS, Kline

    open_time = index * INTERVAL_MS[interval]
    price = Decimal(close)
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=open_time,
        close_time=open_time + INTERVAL_MS[interval] - 1,
        open=Decimal(open_price) if open_price is not None else price,
        high=Decimal(high) if high is not None else price + Decimal("2"),
        low=Decimal(low) if low is not None else price - Decimal("2"),
        close=price,
        volume=Decimal("10"),
    )


def test_strategy_backtest_fetches_history_and_runs_current_realtime_strategy(monkeypatch):
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    requested: list[tuple[str, str, int, int | None, int | None]] = []

    async def fake_fetch_klines(
        symbol: str,
        interval: str,
        limit: int,
        settings=None,
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        requested.append((symbol, interval, limit, start_time, end_time))
        if interval == "4h":
            rows = [
                _kline(symbol, interval, index, close)
                for index, close in zip(range(-6, 0), ["100", "104", "108", "112", "116", "120"])
            ]
        elif interval == "1h":
            rows = [
                _kline(symbol, interval, index, close)
                for index, close in zip(range(-6, 0), ["108", "112", "116", "120", "124", "128"])
            ]
        elif interval == "15m":
            rows = [
                *[
                    _kline(symbol, interval, index, close)
                    for index, close in enumerate(["120", "124", "128", "124"])
                ],
                _kline(symbol, interval, 4, "126", open_price="125"),
                _kline(symbol, interval, 5, "130", open_price="160", high="160", low="125"),
            ]
        else:
            rows = []
        if start_time is None or end_time is None:
            return rows[:limit]
        return [
            row
            for row in rows
            if start_time <= row.open_time <= end_time
        ][:limit]

    monkeypatch.setattr(strategy_backtest, "fetch_klines", fake_fetch_klines)

    result = asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                ema_fast_period=3,
                ema_slow_period=5,
                atr_period=3,
                dmi_period=3,
                swing_lookback=5,
                limit=6,
                history_start_time_ms=-6 * 4 * 60 * 60 * 1000,
                history_end_time_ms=6 * 15 * 60 * 1000 - 1,
                history_cache_dir=None,
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
            )
        )
    )

    assert result.error is None
    assert ("BTCUSDT", "4h", 6, -86400000, -1) in requested
    assert any(request[:3] == ("BTCUSDT", "1h", 6) for request in requested)
    assert any(request[:3] == ("BTCUSDT", "15m", 6) for request in requested)
    assert result.config.ema_fast_period == 3
    assert result.config.ema_slow_period == 5
    assert result.total_trades == 1
    assert result.final_equity == "1010.00"
    assert result.trades[0]["strategy_type"] == "TREND_PULLBACK"


def test_strategy_backtest_defaults_to_perpetual_contract_costs():
    from app.paper.strategy_backtest import StrategyBacktestConfig

    config = StrategyBacktestConfig()

    assert config.maker_fee_rate == Decimal("0.0002")
    assert config.taker_fee_rate == Decimal("0.0005")
    assert config.leverage == Decimal("10")
    assert config.funding_rate == Decimal("0")
    assert config.funding_interval_ms == 8 * 60 * 60 * 1000
    assert config.trend_pullback_take_profit_mode == "TRAILING"
    assert config.max_fee_to_risk_ratio == Decimal("0.25")


def test_strategy_backtest_returns_error_when_historical_fetch_fails(monkeypatch):
    from app.data.binance import BinanceDataError
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    async def fake_fetch_klines(
        symbol: str,
        interval: str,
        limit: int,
        settings=None,
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        raise BinanceDataError("HTTP 451")

    monkeypatch.setattr(strategy_backtest, "fetch_klines", fake_fetch_klines)

    result = asyncio.run(run_strategy_backtest(StrategyBacktestConfig(symbols=("BTCUSDT",), history_cache_dir=None)))

    assert result.error == "HTTP 451"
    assert result.total_trades == 0
    assert result.trades == []


def test_strategy_backtest_paginates_history_window(monkeypatch):
    from app.data.quality import INTERVAL_MS
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    requests: list[tuple[str, str, int, int | None, int | None]] = []

    async def fake_fetch_klines(
        symbol: str,
        interval: str,
        limit: int,
        settings=None,
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        requests.append((symbol, interval, limit, start_time, end_time))
        if start_time is None or end_time is None or start_time > end_time:
            return []
        return [
            _kline(
                symbol=symbol,
                interval=interval,
                index=start_time // INTERVAL_MS[interval],
                close="100",
            )
        ]

    monkeypatch.setattr(strategy_backtest, "fetch_klines", fake_fetch_klines)

    result = asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                history_period="3m",
                history_end_time_ms=90 * 24 * 60 * 60 * 1000,
                history_cache_dir=None,
                limit=1000,
            )
        )
    )

    assert result.error is None
    first_15m = next(request for request in requests if request[1] == "15m")
    assert first_15m == ("BTCUSDT", "15m", 1000, 0, 899999999)
    assert len([request for request in requests if request[1] == "15m"]) > 1


def test_strategy_backtest_reuses_cached_klines_and_fetches_only_missing_tail(monkeypatch, tmp_path):
    from app.data.quality import INTERVAL_MS
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    requests: list[tuple[int | None, int | None]] = []

    async def fake_fetch_klines(
        symbol: str,
        interval: str,
        limit: int,
        settings=None,
        start_time: int | None = None,
        end_time: int | None = None,
    ):
        requests.append((start_time, end_time))
        if start_time is None or end_time is None or start_time > end_time:
            return []
        interval_ms = INTERVAL_MS[interval]
        start_index = start_time // interval_ms
        end_index = end_time // interval_ms
        return [_kline(symbol, interval, index, "100") for index in range(start_index, end_index + 1)]

    monkeypatch.setattr(strategy_backtest, "fetch_klines", fake_fetch_klines)
    base = StrategyBacktestConfig(
        symbols=("BTCUSDT",),
        history_start_time_ms=0,
        history_end_time_ms=4 * INTERVAL_MS["15m"] - 1,
        history_cache_dir=tmp_path / "backtest-klines",
        limit=10,
    )

    asyncio.run(run_strategy_backtest(base))
    first_run_requests = len(requests)
    assert first_run_requests > 0

    asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                ema_fast_period=30,
                ema_slow_period=120,
                history_start_time_ms=0,
                history_end_time_ms=2 * INTERVAL_MS["15m"] - 1,
                history_cache_dir=tmp_path / "backtest-klines",
                limit=10,
            )
        )
    )
    assert len(requests) == first_run_requests

    asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                history_start_time_ms=0,
                history_end_time_ms=5 * INTERVAL_MS["15m"] - 1,
                history_cache_dir=tmp_path / "backtest-klines",
                limit=10,
            )
        )
    )
    assert len(requests) == first_run_requests + 2
    assert requests[-1] == (4 * INTERVAL_MS["15m"], 5 * INTERVAL_MS["15m"] - 1)


def test_archives_strategy_backtest_result_to_database():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.database.models import BacktestRun, BacktestTradeRecord, Base, ConfigSnapshot
    from app.database.repositories import archive_strategy_backtest_result
    from app.paper.strategy_backtest import StrategyBacktestConfig, StrategyBacktestResult

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    result = StrategyBacktestResult(
        config=StrategyBacktestConfig(
            symbols=("BTCUSDT",),
            ema_fast_period=30,
            ema_slow_period=120,
            limit=1500,
            history_period="1y",
        ),
        initial_equity="1000.00",
        final_equity="1297.09",
        total_trades=1,
        wins=1,
        losses=0,
        net_pnl="297.09",
        trades=[
            {
                "symbol": "BTCUSDT",
                "side": "SHORT",
                "strategy_type": "TREND_PULLBACK",
                "entry_time": "1",
                "exit_time": "2",
                "entry_price": "64000",
                "exit_price": "62000",
                "quantity": "0.01",
                "gross_pnl": "20",
                "fees": "1",
                "funding_fee": "0",
                "net_pnl": "19",
                "exit_reason": "TAKE_PROFIT",
            }
        ],
        error=None,
    )

    with Session(engine) as session:
        run_id = archive_strategy_backtest_result(session, result)
        saved_run = session.get(BacktestRun, run_id)
        saved_config = session.execute(select(ConfigSnapshot)).scalar_one()
        saved_trade = session.execute(select(BacktestTradeRecord)).scalar_one()

    assert saved_run is not None
    assert saved_run.name == "web_strategy_backtest"
    assert saved_run.config_snapshot_id == saved_config.id
    assert saved_run.final_equity == Decimal("1297.09")
    assert saved_run.total_trades == 1
    assert saved_config.name == "strategy_backtest"
    assert saved_config.content is not None
    config_payload = json.loads(saved_config.content)
    assert config_payload["ema_fast_period"] == "30"
    assert config_payload["max_fee_to_risk_ratio"] == "0.25"
    assert saved_trade.backtest_run_id == run_id
    assert saved_trade.symbol == "BTCUSDT"
    assert saved_trade.net_pnl == Decimal("19")


def test_strategy_backtest_batch_config_builds_user_selected_parameter_sets():
    from scripts.run_strategy_backtest_batch import (
        StrategyBacktestBatchConfig,
        _build_primary_candidates,
        _build_refinement_candidates,
    )

    config = StrategyBacktestBatchConfig(
        fast_ma_type="MA",
        slow_ma_type="EMA",
        fast_periods=(10, 20),
        slow_periods=(30, 40),
        atr_periods=(10, 14),
        dmi_periods=(12,),
        swing_lookbacks=(15,),
        max_fee_to_risk_ratios=("0.20", "0.25"),
        take_profit_modes=("TRAILING", "FIXED"),
        skip_fast_gte_slow=True,
    )

    primary = list(_build_primary_candidates(config))
    refinement = list(_build_refinement_candidates(primary[0], config))

    assert [(item.fast_period, item.slow_period) for item in primary] == [
        (10, 30),
        (10, 40),
        (20, 30),
        (20, 40),
    ]
    assert primary[0].fast_ma_type == "MA"
    assert primary[0].slow_ma_type == "EMA"
    assert {item.atr_period for item in refinement} == {10, 14}
    assert {item.max_fee_to_risk_ratio for item in refinement} == {"0.20", "0.25"}
    assert {item.trend_pullback_take_profit_mode for item in refinement} == {"TRAILING", "FIXED"}


def test_strategy_backtest_batch_query_builds_config_from_ranges():
    from scripts.run_paper_status_web import _batch_config_from_query

    config = _batch_config_from_query(
        {
            "symbol": ["ETHUSDT"],
            "fast_ma_type": ["EMA"],
            "slow_ma_type": ["MA"],
            "fast_start": ["15"],
            "fast_end": ["25"],
            "fast_step": ["5"],
            "slow_start": ["60"],
            "slow_end": ["120"],
            "slow_step": ["30"],
            "history_period": ["2y"],
            "atr_periods": ["10,14"],
            "dmi_periods": ["12,16"],
            "swing_lookbacks": ["15,20"],
            "max_fee_to_risk_ratios": ["0.20,0.25"],
            "take_profit_modes": ["TRAILING,FIXED"],
            "skip_fast_gte_slow": ["1"],
        }
    )

    assert config.symbol == "ETHUSDT"
    assert config.fast_periods == (15, 20, 25)
    assert config.slow_periods == (60, 90, 120)
    assert config.history_period == "2y"
    assert config.history_window_ms == 2 * 365 * 24 * 60 * 60 * 1000
    assert config.atr_periods == (10, 14)
    assert config.dmi_periods == (12, 16)
    assert config.swing_lookbacks == (15, 20)
    assert config.max_fee_to_risk_ratios == ("0.20", "0.25")
    assert config.take_profit_modes == ("TRAILING", "FIXED")
    assert config.skip_fast_gte_slow is True


def test_strategy_backtest_batch_skips_parameter_set_already_archived_in_database(monkeypatch, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    import scripts.run_strategy_backtest_batch as batch
    from app.database.models import Base
    from app.database.repositories import archive_strategy_backtest_result
    from app.paper.strategy_backtest import StrategyBacktestConfig, StrategyBacktestResult
    from scripts.run_strategy_backtest_batch import BacktestWindow, ParameterSet

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    window = BacktestWindow(
        start_time_ms=0,
        end_time_ms=1000,
        latest_close_time_by_interval={"4h": 1000, "1h": 1000, "15m": 1000},
    )
    params = ParameterSet(
        fast_period=15,
        slow_period=60,
        fast_ma_type="EMA",
        slow_ma_type="MA",
        atr_period=14,
        dmi_period=14,
        swing_lookback=20,
        max_fee_to_risk_ratio="0.25",
        trend_pullback_take_profit_mode="TRAILING",
    )
    existing_result = StrategyBacktestResult(
        config=StrategyBacktestConfig(
            symbols=("BTCUSDT",),
            fast_ma_type="EMA",
            slow_ma_type="MA",
            ema_fast_period=15,
            ema_slow_period=60,
            atr_period=14,
            dmi_period=14,
            swing_lookback=20,
            limit=1500,
            history_period="1y",
            history_start_time_ms=0,
            history_end_time_ms=1000,
            history_cache_dir=tmp_path / "cache",
            max_fee_to_risk_ratio=Decimal("0.25"),
            trend_pullback_take_profit_mode="TRAILING",
        ),
        initial_equity="1000.00",
        final_equity="1111.00",
        total_trades=3,
        wins=2,
        losses=1,
        net_pnl="111.00",
        trades=[],
        error=None,
    )
    with Session(engine) as session:
        archived_run_id = archive_strategy_backtest_result(session, existing_result)

    async def fail_if_called(_config):
        raise AssertionError("run_strategy_backtest should not run when database already has this config")

    monkeypatch.setattr(batch, "run_strategy_backtest", fail_if_called)

    records = batch._run_phase(
        phase="primary",
        candidates=[params],
        checkpoint={"records": {}},
        workspace=tmp_path,
        cache_dir=tmp_path / "cache",
        session_factory=session_factory,
        symbol="BTCUSDT",
        window=window,
        history_period="1y",
        rerun_completed=False,
        retry_failed=False,
    )

    assert records[0]["status"] == "success"
    assert records[0]["source"] == "existing_database"
    assert records[0]["archived_run_id"] == archived_run_id
    assert records[0]["final_equity"] == "1111.00"
    assert records[0]["win_rate"] == "66.67"
