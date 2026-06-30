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
    assert result.strategy_metrics["TREND_PULLBACK"]["trade_count"] == 1
    assert result.strategy_metrics["TREND_PULLBACK"]["wins"] == 1
    assert result.bucket_metrics["LEGACY"]["trade_count"] == 1
    assert result.symbol_metrics["BTCUSDT"]["trade_count"] == 1
    assert result.symbol_metrics["BTCUSDT"]["net_pnl"] == "10.00"
    assert result.max_drawdown == "0.00"
    assert result.max_drawdown_pct == "0.00"
    assert result.profit_loss_ratio == "∞"
    assert result.trades[0]["strategy_type"] == "TREND_PULLBACK"


def test_strategy_backtest_orders_multitimeframe_events_by_close_time():
    from app.paper.strategy_backtest import _sort_backtest_klines_for_event_replay

    daily = _kline("BTCUSDT", "1d", 0, "100")
    fifteen_before_daily_close = _kline("BTCUSDT", "15m", 1, "101")
    fifteen_after_daily_close = _kline("BTCUSDT", "15m", 96, "102")

    ordered = _sort_backtest_klines_for_event_replay(
        [fifteen_after_daily_close, daily, fifteen_before_daily_close]
    )

    assert ordered == [fifteen_before_daily_close, daily, fifteen_after_daily_close]


def test_strategy_backtest_drawdown_metrics_follow_closed_equity_curve():
    from app.paper.strategy_backtest import _drawdown_metrics
    from app.paper.trading import PaperFill

    fills = [
        PaperFill(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="SHORT_DAY_CORE",
            entry_time=0,
            exit_time=3,
            entry_price=Decimal("100"),
            exit_price=Decimal("90"),
            quantity=Decimal("1"),
            gross_pnl=Decimal("-100"),
            fees=Decimal("0"),
            net_pnl=Decimal("-100"),
            exit_reason="STOP_LOSS",
        ),
        PaperFill(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="SHORT_DAY_CORE",
            entry_time=0,
            exit_time=1,
            entry_price=Decimal("100"),
            exit_price=Decimal("120"),
            quantity=Decimal("1"),
            gross_pnl=Decimal("200"),
            fees=Decimal("0"),
            net_pnl=Decimal("200"),
            exit_reason="TAKE_PROFIT",
        ),
        PaperFill(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="SHORT_DAY_CORE",
            entry_time=0,
            exit_time=2,
            entry_price=Decimal("100"),
            exit_price=Decimal("80"),
            quantity=Decimal("1"),
            gross_pnl=Decimal("-250"),
            fees=Decimal("0"),
            net_pnl=Decimal("-250"),
            exit_reason="STOP_LOSS",
        ),
    ]

    max_drawdown, max_drawdown_pct = _drawdown_metrics(Decimal("1000"), fills)

    assert max_drawdown == "350.00"
    assert max_drawdown_pct == "29.17"


def test_strategy_backtest_profit_loss_ratio_uses_average_win_and_loss():
    from app.paper.strategy_backtest import _profit_loss_ratio
    from app.paper.trading import PaperFill

    fills = [
        PaperFill(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="SHORT_DAY_CORE",
            entry_time=0,
            exit_time=1,
            entry_price=Decimal("100"),
            exit_price=Decimal("120"),
            quantity=Decimal("1"),
            gross_pnl=Decimal("300"),
            fees=Decimal("0"),
            net_pnl=Decimal("300"),
            exit_reason="TAKE_PROFIT",
        ),
        PaperFill(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="SHORT_DAY_CORE",
            entry_time=0,
            exit_time=2,
            entry_price=Decimal("100"),
            exit_price=Decimal("120"),
            quantity=Decimal("1"),
            gross_pnl=Decimal("100"),
            fees=Decimal("0"),
            net_pnl=Decimal("100"),
            exit_reason="TAKE_PROFIT",
        ),
        PaperFill(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="SHORT_DAY_CORE",
            entry_time=0,
            exit_time=3,
            entry_price=Decimal("100"),
            exit_price=Decimal("90"),
            quantity=Decimal("1"),
            gross_pnl=Decimal("-100"),
            fees=Decimal("0"),
            net_pnl=Decimal("-100"),
            exit_reason="STOP_LOSS",
        ),
    ]

    assert _profit_loss_ratio(fills) == "2.00"


def test_strategy_backtest_symbol_metrics_group_fills_by_symbol():
    from app.paper.strategy_backtest import _symbol_metrics
    from app.paper.trading import PaperFill

    fills = [
        PaperFill(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="SHORT_DAY_CORE",
            entry_time=0,
            exit_time=1,
            entry_price=Decimal("100"),
            exit_price=Decimal("120"),
            quantity=Decimal("1"),
            gross_pnl=Decimal("30"),
            fees=Decimal("0"),
            net_pnl=Decimal("30"),
            exit_reason="TAKE_PROFIT",
        ),
        PaperFill(
            symbol="ETHUSDT",
            side="SHORT",
            strategy_type="SHORT_DAY_CORE",
            entry_time=0,
            exit_time=2,
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            quantity=Decimal("1"),
            gross_pnl=Decimal("-10"),
            fees=Decimal("0"),
            net_pnl=Decimal("-10"),
            exit_reason="STOP_LOSS",
        ),
    ]

    metrics = _symbol_metrics(fills)

    assert metrics["BTCUSDT"] == {"trade_count": 1, "wins": 1, "losses": 0, "net_pnl": "30.00"}
    assert metrics["ETHUSDT"] == {"trade_count": 1, "wins": 0, "losses": 1, "net_pnl": "-10.00"}


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
    assert config.enable_reversal_probe is False
    assert config.pullback_zone_atr_multiplier == Decimal("1")
    assert config.require_pullback_close_beyond_fast_ma is False


def test_strategy_backtest_config_passes_trigger_options_to_realtime_config(monkeypatch):
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

    captured = {}

    async def fake_fetch_backtest_klines(config):
        return []

    class FakeEngine:
        def __init__(self, config):
            self._config = config

        def on_kline(self, kline):
            return None

        def on_signal(self, kline, signal):
            return None

        def snapshot(self):
            from app.paper.persistence import PaperSnapshot

            return PaperSnapshot(
                equity=Decimal("1000"),
                open_position=None,
                fills=[],
                rejected_signals=0,
                last_update_at_ms=None,
                runtime_started_at_ms=None,
                signal_evaluations=[],
            )

    def fake_build_default_realtime_signal_fn(config, warmup_klines=()):
        captured["config"] = config

        def signal_fn(kline, has_position):
            from app.strategy.signal_router import StrategySignal

            return StrategySignal(action="WAIT", strategy_type="SYSTEM", reason=[])

        return signal_fn

    monkeypatch.setattr(strategy_backtest, "_fetch_backtest_klines", fake_fetch_backtest_klines)
    monkeypatch.setattr(strategy_backtest, "PaperTradingEngine", FakeEngine)
    monkeypatch.setattr(strategy_backtest, "build_default_realtime_signal_fn", fake_build_default_realtime_signal_fn)

    result = asyncio.run(
        run_strategy_backtest(
            StrategyBacktestConfig(
                pullback_zone_atr_multiplier=Decimal("0.5"),
                require_pullback_close_beyond_fast_ma=True,
                enable_reversal_probe=False,
            )
        )
    )

    assert result.error is None
    assert captured["config"].pullback_zone_atr_multiplier == Decimal("0.5")
    assert captured["config"].require_pullback_close_beyond_fast_ma is True
    assert captured["config"].enable_reversal_probe is False


def test_strategy_backtest_passes_open_bucket_context_to_realtime_signal(monkeypatch):
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest
    from app.strategy.signal_router import StrategySignal

    observed_contexts = []

    async def fake_fetch_backtest_klines(config):
        return [
            _kline("BTCUSDT", "15m", 0, "100", high="102", low="98"),
            _kline("BTCUSDT", "15m", 1, "100", high="102", low="98"),
        ]

    def fake_build_default_realtime_signal_fn(config, warmup_klines=()):
        def signal_fn(kline, has_position, context=None):
            observed_contexts.append(context)
            if not has_position:
                return StrategySignal(
                    action="LONG_ENTRY",
                    strategy_type="LONG_DAY_CORE",
                    bucket="DAY_CORE",
                    entry_price=Decimal("100"),
                    stop_loss=Decimal("92"),
                    take_profit=Decimal("116"),
                    risk_pct=Decimal("0.005"),
                    reason=["open core"],
                )
            return StrategySignal(action="WAIT", strategy_type="SYSTEM", reason=["inspect context"])

        return signal_fn

    monkeypatch.setattr(strategy_backtest, "_fetch_backtest_klines", fake_fetch_backtest_klines)
    monkeypatch.setattr(strategy_backtest, "build_default_realtime_signal_fn", fake_build_default_realtime_signal_fn)

    result = asyncio.run(run_strategy_backtest(StrategyBacktestConfig()))

    assert result.error is None
    assert observed_contexts[1] is not None
    assert observed_contexts[1].open_buckets == ("DAY_CORE",)
    assert observed_contexts[1].open_strategy_types == ("LONG_DAY_CORE",)


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
    assert config_payload["enable_reversal_probe"] == "False"
    assert config_payload["pullback_zone_atr_multiplier"] == "1"
    assert config_payload["require_pullback_close_beyond_fast_ma"] == "False"
    assert saved_trade.backtest_run_id == run_id
    assert saved_trade.symbol == "BTCUSDT"
    assert saved_trade.net_pnl == Decimal("19")


def test_strategy_backtest_batch_config_builds_user_selected_parameter_sets():
    from scripts.run_strategy_backtest_batch import StrategyBacktestBatchConfig, _build_primary_candidates

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
        pullback_zone_atr_multipliers=("1", "0.5"),
        require_pullback_close_beyond_fast_ma_options=(False, True),
        enable_reversal_probe_options=(True, False),
        skip_fast_gte_slow=True,
    )

    primary = list(_build_primary_candidates(config))

    assert len(primary) == 256
    assert {(item.fast_period, item.slow_period) for item in primary} == {
        (10, 30),
        (10, 40),
        (20, 30),
        (20, 40),
    }
    assert {item.fast_ma_type for item in primary} == {"MA"}
    assert {item.slow_ma_type for item in primary} == {"EMA"}
    assert {item.atr_period for item in primary} == {10, 14}
    assert {item.dmi_period for item in primary} == {12}
    assert {item.swing_lookback for item in primary} == {15}
    assert {item.max_fee_to_risk_ratio for item in primary} == {"0.20", "0.25"}
    assert {item.trend_pullback_take_profit_mode for item in primary} == {"TRAILING", "FIXED"}
    assert {item.pullback_zone_atr_multiplier for item in primary} == {"1", "0.5"}
    assert {item.require_pullback_close_beyond_fast_ma for item in primary} == {False, True}
    assert {item.enable_reversal_probe for item in primary} == {False, True}


def test_strategy_backtest_batch_primary_candidates_honor_single_dmi_input():
    from scripts.run_paper_status_web import _batch_config_from_query
    from scripts.run_strategy_backtest_batch import _build_primary_candidates

    config = _batch_config_from_query(
        {
            "fast_start": ["15"],
            "fast_end": ["15"],
            "slow_start": ["60"],
            "slow_end": ["90"],
            "slow_step": ["30"],
            "atr_periods": ["14"],
            "dmi_periods": ["12"],
            "swing_lookbacks": ["20"],
            "max_fee_to_risk_ratios": ["0.25"],
            "take_profit_modes": ["TRAILING"],
            "pullback_zone_atr_multipliers": ["0.5"],
            "require_pullback_close_beyond_fast_ma_options": ["true"],
            "enable_reversal_probe_options": ["false"],
        }
    )

    primary = list(_build_primary_candidates(config))

    assert [item.label() for item in primary] == [
        (
            "EMA15/MA60 | ATR 14 | DMI 12 | Swing 20 | Fee/Risk 0.25 | TP TRAILING"
            " | ZoneATR 0.5 | CloseBeyondMA True | Reversal False"
        ),
        (
            "EMA15/MA90 | ATR 14 | DMI 12 | Swing 20 | Fee/Risk 0.25 | TP TRAILING"
            " | ZoneATR 0.5 | CloseBeyondMA True | Reversal False"
        ),
    ]


def test_strategy_backtest_batch_query_defaults_match_page_defaults():
    from scripts.run_paper_status_web import _batch_config_from_query

    config = _batch_config_from_query({})

    assert config.slow_periods == (30, 60, 90, 120, 150, 180, 200)
    assert config.atr_periods == (12, 14)
    assert config.dmi_periods == (12, 14)
    assert config.swing_lookbacks == (20, 30)
    assert config.max_fee_to_risk_ratios == ("0.25", "0")
    assert config.pullback_zone_atr_multipliers == ("1",)
    assert config.require_pullback_close_beyond_fast_ma_options == (False,)
    assert config.enable_reversal_probe_options == (False,)
    assert config.skip_fast_gte_slow is True


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
            enable_reversal_probe=False,
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


def test_strategy_backtest_batch_reruns_stale_checkpoint_success_missing_from_database(monkeypatch, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    import scripts.run_strategy_backtest_batch as batch
    from app.database.models import BacktestRun, Base
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
    run_key = batch._run_key("primary", params)
    checkpoint = {
        "records": {
            run_key: {
                "phase": "primary",
                "run_key": run_key,
                "status": "success",
                "params": {},
            }
        }
    }
    calls = 0

    async def fake_run_strategy_backtest(config):
        nonlocal calls
        calls += 1
        return StrategyBacktestResult(
            config=StrategyBacktestConfig(
                symbols=("BTCUSDT",),
                fast_ma_type=config.fast_ma_type,
                slow_ma_type=config.slow_ma_type,
                ema_fast_period=config.ema_fast_period,
                ema_slow_period=config.ema_slow_period,
                atr_period=config.atr_period,
                dmi_period=config.dmi_period,
                swing_lookback=config.swing_lookback,
                limit=config.limit,
                history_period=config.history_period,
                history_start_time_ms=config.history_start_time_ms,
                history_end_time_ms=config.history_end_time_ms,
                history_cache_dir=config.history_cache_dir,
                max_fee_to_risk_ratio=config.max_fee_to_risk_ratio,
                trend_pullback_take_profit_mode=config.trend_pullback_take_profit_mode,
            ),
            initial_equity="1000.00",
            final_equity="1005.00",
            total_trades=1,
            wins=1,
            losses=0,
            net_pnl="5.00",
            trades=[],
            error=None,
        )

    monkeypatch.setattr(batch, "run_strategy_backtest", fake_run_strategy_backtest)
    logs: list[str] = []

    records = batch._run_phase(
        phase="primary",
        candidates=[params],
        checkpoint=checkpoint,
        workspace=tmp_path,
        cache_dir=tmp_path / "cache",
        session_factory=session_factory,
        symbol="BTCUSDT",
        window=window,
        history_period="1y",
        rerun_completed=False,
        retry_failed=False,
        log_callback=logs.append,
    )

    with Session(engine) as session:
        saved_runs = session.query(BacktestRun).all()

    assert calls == 1
    assert records[0]["status"] == "success"
    assert records[0]["final_equity"] == "1005.00"
    assert len(saved_runs) == 1
    assert any("checkpoint success missing from database" in line for line in logs)


def test_strategy_backtest_batch_phase_emits_logs_and_honors_stop_event(tmp_path):
    import threading

    import scripts.run_strategy_backtest_batch as batch
    from scripts.run_strategy_backtest_batch import BacktestWindow, ParameterSet

    stop_event = threading.Event()
    stop_event.set()
    logs: list[str] = []

    records = batch._run_phase(
        phase="primary",
        candidates=[ParameterSet(fast_period=15, slow_period=60)],
        checkpoint={"records": {}},
        workspace=tmp_path,
        cache_dir=tmp_path / "cache",
        session_factory=None,
        symbol="BTCUSDT",
        window=BacktestWindow(
            start_time_ms=0,
            end_time_ms=1000,
            latest_close_time_by_interval={"4h": 1000, "1h": 1000, "15m": 1000},
        ),
        history_period="1y",
        rerun_completed=False,
        retry_failed=False,
        log_callback=logs.append,
        stop_event=stop_event,
    )

    assert records == []
    assert any("停止请求已收到" in line for line in logs)


def test_batch_backtest_job_manager_starts_logs_and_stops(monkeypatch):
    import time

    import scripts.run_paper_status_web as web
    from scripts.run_strategy_backtest_batch import StrategyBacktestBatchConfig

    entered = False

    def fake_run_strategy_backtest_batch(config, log_callback=None, stop_event=None):
        nonlocal entered
        entered = True
        assert config.symbol == "BTCUSDT"
        assert log_callback is not None
        assert stop_event is not None
        log_callback("[run  1/1] primary EMA15/MA30")
        while not stop_event.is_set():
            time.sleep(0.01)
        log_callback("停止请求已收到，当前批量回测将在安全点退出。")
        return {"primary": {"success_runs": 0, "total_runs": 0}, "refinement": {}}

    monkeypatch.setattr(web, "run_strategy_backtest_batch", fake_run_strategy_backtest_batch, raising=False)
    manager = web.BatchBacktestJobManager()

    started = manager.start(StrategyBacktestBatchConfig(symbol="BTCUSDT"))
    time.sleep(0.05)
    stopped = manager.stop()
    for _ in range(50):
        status = manager.status()
        if not status["running"]:
            break
        time.sleep(0.01)

    status = manager.status()
    assert started is True
    assert stopped is True
    assert entered is True
    assert status["running"] is False
    assert status["stop_requested"] is True
    assert any("[run  1/1]" in line for line in status["logs"])
    assert status["analysis"]["primary"]["success_runs"] == 0


def test_batch_backtest_job_manager_auto_stops_when_all_combinations_finish(monkeypatch):
    import time

    import scripts.run_paper_status_web as web
    from scripts.run_strategy_backtest_batch import StrategyBacktestBatchConfig

    def fake_run_strategy_backtest_batch(config, log_callback=None, stop_event=None):
        assert stop_event is not None
        assert stop_event.is_set() is False
        log_callback("[summary] all combinations completed")
        return {"primary": {"success_runs": 1, "total_runs": 1}, "refinement": {}}

    monkeypatch.setattr(web, "run_strategy_backtest_batch", fake_run_strategy_backtest_batch, raising=False)
    manager = web.BatchBacktestJobManager()

    assert manager.start(StrategyBacktestBatchConfig(symbol="BTCUSDT")) is True
    for _ in range(50):
        status = manager.status()
        if not status["running"]:
            break
        time.sleep(0.01)

    status = manager.status()
    assert status["running"] is False
    assert status["stop_requested"] is False
    assert status["finished_at_ms"] is not None
    assert status["analysis"]["primary"]["success_runs"] == 1
    assert any("批量回测后台任务已结束" in line for line in status["logs"])


def test_batch_backtest_job_manager_coalesces_countdown_logs():
    import scripts.run_paper_status_web as web

    manager = web.BatchBacktestJobManager()

    manager._append_log("[run  1/1] primary EMA15/MA30")
    manager._append_log("         本轮倒计时: 剩余 00:03 / 预计 00:05")
    manager._append_log("         本轮倒计时: 剩余 00:02 / 预计 00:05")
    manager._append_log("         本轮倒计时: 剩余 00:01 / 预计 00:05")
    manager._append_log("         本轮实际用时=00:05")

    logs = manager.status()["logs"]
    countdown_logs = [line for line in logs if "本轮倒计时" in line]
    assert countdown_logs == ["         本轮倒计时: 剩余 00:01 / 预计 00:05"]
    assert logs == [
        "[run  1/1] primary EMA15/MA30",
        "         本轮倒计时: 剩余 00:01 / 预计 00:05",
        "         本轮实际用时=00:05",
    ]
