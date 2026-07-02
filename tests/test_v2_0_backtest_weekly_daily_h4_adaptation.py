def test_strategy_backtest_config_payload_uses_weekly_daily_h4_kernel():
    from app.database.repositories import strategy_backtest_config_payload
    from app.paper.strategy_backtest import StrategyBacktestConfig

    payload = strategy_backtest_config_payload(StrategyBacktestConfig())

    assert payload["strategy_kernel"] == "WEEKLY_DAILY_H4_V1"
    assert payload["trade_policy_version"] == "INDEPENDENT_TIMELINES_V5"
    assert payload["timeframes"] == "1w,1d,4h"
    assert payload["weekly_risk_pct"] == "0.008"
    assert payload["daily_risk_pct"] == "0.005"
    assert payload["h4_risk_pct"] == "0.002"
    assert payload["weekly_margin_pct"] == "0.10"
    assert payload["target_risk_reward"] == "2"
    assert payload["daily_exit_policy"] == "FULL_REVERSAL"
    assert payload["h4_rebound_adx_block_threshold"] == "20"
    assert payload["stop_atr_multiplier"] == "1.5"
    assert payload["max_same_direction_positions_per_level"] == "2"
    assert payload["weekly_max_same_direction_positions"] == "2"
    assert payload["daily_max_same_direction_positions"] == "1"
    assert payload["h4_max_same_direction_positions"] == "2"
    assert payload["allow_same_direction_add_positions"] == "true"
    assert "enable_reversal_probe" not in payload
    assert "pullback_zone_atr_multiplier" not in payload
    assert "require_pullback_close_beyond_fast_ma" not in payload


def test_batch_backtest_script_uses_weekly_daily_h4_terms_only():
    import scripts.run_strategy_backtest_batch as batch

    parameter_set = batch.ParameterSet(fast_period=15, slow_period=60)

    assert batch.SUPPORTED_INTERVALS == ("1w", "1d", "4h")
    assert "WEEKLY_DAILY_H4_V1" in parameter_set.label()
    assert "INDEPENDENT_TIMELINES_V5" in parameter_set.label()
    assert "RR 2" in parameter_set.label()
    assert "DailyExit FULL_REVERSAL" in parameter_set.label()
    assert "H4ADX 20" in parameter_set.label()
    assert "StopATR 1.5" in parameter_set.label()
    assert "Same W/D/H4 2/1/2" in parameter_set.label()
    assert "independent_timelines_v5" in parameter_set.key()
    assert "rr2" in parameter_set.key()
    assert "dailyexitfull_reversal" in parameter_set.key()
    assert "h4adx20" in parameter_set.key()
    assert "stopatr1.5" in parameter_set.key()
    assert "same2" in parameter_set.key()
    assert "wsame2" in parameter_set.key()
    assert "dsame1" in parameter_set.key()
    assert "h4same2" in parameter_set.key()
    assert "Reversal" not in parameter_set.label()
    assert "ZoneATR" not in parameter_set.label()
    assert "CloseBeyondMA" not in parameter_set.label()


def test_backtest_pages_show_new_kernel_not_old_layered_bucket_terms():
    from app.paper.web_status import render_strategy_backtest_batch_html, render_strategy_backtest_html

    backtest_html = render_strategy_backtest_html()
    batch_html = render_strategy_backtest_batch_html()
    combined = backtest_html + batch_html

    assert "WEEKLY_DAILY_H4_V1" in combined
    assert "三条独立时间线：1w 周线 / 1d 日线 / 4h" in combined
    assert "独立时间线策略参数" in combined
    assert "4h 执行" not in combined
    assert "Bucket" not in combined
    assert "分层策略" not in combined
    assert "Reversal" not in combined
    assert "趋势转换试仓" not in combined


def test_backtest_page_exposes_timeline_risk_budget_inputs():
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html()

    assert 'name="weekly_risk_pct"' in html
    assert 'value="0.008"' in html
    assert 'name="daily_risk_pct"' in html
    assert 'value="0.005"' in html
    assert 'name="h4_risk_pct"' in html
    assert 'value="0.002"' in html
    assert 'name="weekly_margin_pct"' in html
    assert 'value="0.10"' in html
    assert "周线保证金预算" in html
    assert "周线风险预算" in html
    assert "日线风险预算" in html
    assert "4H风险预算" in html
    assert "周线风险</label>" not in html


def test_backtest_query_parses_layered_risk_pct_inputs():
    from scripts.run_paper_status_web import _backtest_config_from_query

    config = _backtest_config_from_query(
        {
            "weekly_risk_pct": ["0.01"],
            "daily_risk_pct": ["0.006"],
            "h4_risk_pct": ["0.0025"],
            "weekly_margin_pct": ["0.12"],
        }
    )

    assert str(config.weekly_risk_pct) == "0.01"
    assert str(config.daily_risk_pct) == "0.006"
    assert str(config.h4_risk_pct) == "0.0025"
    assert str(config.weekly_margin_pct) == "0.12"


def test_backtest_query_parses_strategy_tuning_inputs():
    from scripts.run_paper_status_web import _backtest_config_from_query

    config = _backtest_config_from_query(
        {
            "target_risk_reward": ["3"],
            "daily_exit_policy": ["NONE"],
            "h4_rebound_adx_block_threshold": ["32"],
            "stop_atr_multiplier": ["2.25"],
            "max_same_direction_positions_per_level": ["3"],
            "weekly_max_same_direction_positions": ["2"],
            "daily_max_same_direction_positions": ["1"],
            "h4_max_same_direction_positions": ["4"],
            "allow_same_direction_add_positions": ["0"],
        }
    )

    assert str(config.target_risk_reward) == "3"
    assert config.daily_exit_policy == "NONE"
    assert str(config.h4_rebound_adx_block_threshold) == "32"
    assert str(config.stop_atr_multiplier) == "2.25"
    assert config.max_same_direction_positions_per_level == 3
    assert config.weekly_max_same_direction_positions == 2
    assert config.daily_max_same_direction_positions == 1
    assert config.h4_max_same_direction_positions == 4
    assert config.allow_same_direction_add_positions is False


def test_batch_query_parses_strategy_tuning_grids():
    from scripts.run_paper_status_web import _batch_config_from_query

    config = _batch_config_from_query(
        {
            "target_risk_rewards": ["2,3"],
            "daily_exit_policies": ["FULL_REVERSAL"],
            "h4_rebound_adx_block_thresholds": ["20,25,30"],
            "stop_atr_multipliers": ["1,1.5,2"],
            "max_same_direction_positions_per_levels": ["1,2"],
            "weekly_max_same_direction_positions": ["2,3"],
            "daily_max_same_direction_positions": ["1"],
            "h4_max_same_direction_positions": ["2,4"],
        }
    )

    assert config.target_risk_rewards == ("2", "3")
    assert config.daily_exit_policies == ("FULL_REVERSAL",)
    assert config.h4_rebound_adx_block_thresholds == ("20", "25", "30")
    assert config.stop_atr_multipliers == ("1", "1.5", "2")
    assert config.max_same_direction_positions_per_levels == (1, 2)
    assert config.weekly_max_same_direction_positions == (2, 3)
    assert config.daily_max_same_direction_positions == (1,)
    assert config.h4_max_same_direction_positions == (2, 4)


def test_backtest_applies_risk_pct_by_position_level():
    from decimal import Decimal

    from app.paper.strategy_backtest import StrategyBacktestConfig, _apply_backtest_level_risk
    from app.strategy.signal_router import StrategySignal

    config = StrategyBacktestConfig(
        weekly_risk_pct=Decimal("0.01"),
        daily_risk_pct=Decimal("0.006"),
        h4_risk_pct=Decimal("0.0025"),
    )

    weekly = _apply_backtest_level_risk(
        StrategySignal(action="SHORT_ENTRY", strategy_type="WEEKLY_SHORT_TREND", reason=[], position_level="WEEKLY"),
        config,
    )
    daily = _apply_backtest_level_risk(
        StrategySignal(action="SHORT_ENTRY", strategy_type="DAILY_SHORT_TREND", reason=[], bucket="DAILY"),
        config,
    )
    h4 = _apply_backtest_level_risk(
        StrategySignal(action="LONG_ENTRY", strategy_type="H4_LONG_BREAKOUT", reason=[], position_level="H4"),
        config,
    )
    wait = _apply_backtest_level_risk(
        StrategySignal(action="WAIT", strategy_type="SYSTEM", reason=[], position_level="WEEKLY"),
        config,
    )

    assert weekly.risk_pct == Decimal("0.01")
    assert daily.risk_pct == Decimal("0.006")
    assert h4.risk_pct == Decimal("0.0025")
    assert wait.risk_pct is None


def test_strategy_backtest_fetches_warmup_before_selected_window(monkeypatch):
    import asyncio

    from app.data.quality import INTERVAL_MS
    from app.paper import strategy_backtest
    from app.paper.strategy_backtest import StrategyBacktestConfig

    calls = []

    async def fake_fetch_interval_pages(symbol, interval, limit, start_time, end_time, cache_dir):
        calls.append((symbol, interval, start_time, end_time))
        return []

    monkeypatch.setattr(strategy_backtest, "_fetch_interval_pages", fake_fetch_interval_pages)

    trading_start = INTERVAL_MS["1w"] * 100
    trading_end = trading_start + INTERVAL_MS["1w"] * 52
    asyncio.run(
        strategy_backtest._fetch_backtest_kline_sets(
            StrategyBacktestConfig(
                history_start_time_ms=trading_start,
                history_end_time_ms=trading_end,
                ema_slow_period=60,
                history_cache_dir=None,
            )
        )
    )

    weekly_call = next(call for call in calls if call[1] == "1w")
    assert weekly_call[2] <= trading_start - INTERVAL_MS["1w"] * 60
    assert weekly_call[3] == trading_end


def test_strategy_backtest_splits_warmup_from_replay_window():
    from decimal import Decimal

    from app.data.quality import INTERVAL_MS, Kline
    from app.paper.strategy_backtest import _split_warmup_and_replay_klines

    trading_start = INTERVAL_MS["1d"] * 10

    def row(index: int) -> Kline:
        open_time = INTERVAL_MS["1d"] * index
        return Kline(
            symbol="BTCUSDT",
            interval="1d",
            open_time=open_time,
            close_time=open_time + INTERVAL_MS["1d"] - 1,
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("1"),
        )

    warmup, replay = _split_warmup_and_replay_klines(
        [row(8), row(9), row(10), row(11)],
        trading_start_time_ms=trading_start,
    )

    assert [kline.open_time for kline in warmup] == [INTERVAL_MS["1d"] * 8, INTERVAL_MS["1d"] * 9]
    assert [kline.open_time for kline in replay] == [INTERVAL_MS["1d"] * 10, INTERVAL_MS["1d"] * 11]


def test_batch_backtest_window_tracks_warmup_for_database_and_cache():
    from app.data.quality import INTERVAL_MS
    import scripts.run_strategy_backtest_batch as batch

    trading_start = INTERVAL_MS["1w"] * 100
    window = batch.BacktestWindow(
        start_time_ms=trading_start,
        end_time_ms=trading_start + INTERVAL_MS["1w"] * 52,
        latest_close_time_by_interval={"1w": 1, "1d": 1, "4h": 1},
    )

    warmed = batch._with_warmup_window(
        window,
        batch.StrategyBacktestBatchConfig(
            fast_periods=(15,),
            slow_periods=(60,),
            atr_periods=(14,),
            dmi_periods=(12,),
            swing_lookbacks=(20,),
        ),
    )

    assert warmed.start_time_ms == trading_start
    assert warmed.warmup_start_time_ms <= trading_start - INTERVAL_MS["1w"] * 60
    checkpoint = batch._initial_checkpoint(symbol="BTCUSDT", workspace=batch.ROOT, window=warmed)
    assert checkpoint["window"]["warmup_start_time_ms"] == warmed.warmup_start_time_ms


def test_recent_backtest_summaries_hide_legacy_policy_archives():
    from decimal import Decimal

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.database.models import BacktestRun, Base, ConfigSnapshot
    from app.database.repositories import list_strategy_backtest_summaries

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        legacy_config = ConfigSnapshot(
            name="strategy_backtest",
            version="v1",
            content_hash="legacy",
            content='{"strategy_kernel":"WEEKLY_DAILY_H4_V1","timeframes":"1w,1d,4h","symbols":"BTCUSDT"}',
        )
        session.add(legacy_config)
        session.flush()
        session.add(
            BacktestRun(
                name="web_strategy_backtest",
                config_snapshot_id=legacy_config.id,
                initial_equity=Decimal("1000"),
                final_equity=Decimal("1000"),
                total_trades=0,
                wins=0,
                losses=0,
                net_pnl=Decimal("0"),
            )
        )
        session.commit()

        summaries = list_strategy_backtest_summaries(session)

    assert summaries == []


def test_batch_window_validation_accepts_exchange_aligned_weekly_klines():
    from decimal import Decimal

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.data.quality import INTERVAL_MS, Kline
    from app.database.models import Base
    from app.database.repositories import upsert_klines
    import scripts.run_strategy_backtest_batch as batch

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    def rows(interval: str, count: int, offset: int = 0) -> list[Kline]:
        interval_ms = INTERVAL_MS[interval]
        output = []
        for index in range(count):
            open_time = offset + index * interval_ms
            output.append(
                Kline(
                    symbol="BTCUSDT",
                    interval=interval,
                    open_time=open_time,
                    close_time=open_time + interval_ms - 1,
                    open=Decimal("100"),
                    high=Decimal("102"),
                    low=Decimal("99"),
                    close=Decimal("101"),
                    volume=Decimal("1"),
                )
            )
        return output

    monday_offset = 3 * 24 * 60 * 60 * 1000
    with Session(engine) as session:
        upsert_klines(session, rows("1w", 80, offset=monday_offset))
        upsert_klines(session, rows("1d", 600))
        upsert_klines(session, rows("4h", 3600))
        window = batch._resolve_backtest_window(
            session,
            "BTCUSDT",
            history_window_ms=52 * INTERVAL_MS["1w"],
        )

    assert window.start_time_ms < window.end_time_ms


def test_runtime_events_cli_labels_bucket_as_position_level():
    from scripts.show_paper_runtime_events import format_paper_runtime_events

    assert "层级" in format_paper_runtime_events([])
