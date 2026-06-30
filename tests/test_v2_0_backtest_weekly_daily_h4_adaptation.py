def test_strategy_backtest_config_payload_uses_weekly_daily_h4_kernel():
    from app.database.repositories import strategy_backtest_config_payload
    from app.paper.strategy_backtest import StrategyBacktestConfig

    payload = strategy_backtest_config_payload(StrategyBacktestConfig())

    assert payload["strategy_kernel"] == "WEEKLY_DAILY_H4_V1"
    assert payload["timeframes"] == "1w,1d,4h"
    assert payload["weekly_risk_pct"] == "0.008"
    assert payload["daily_risk_pct"] == "0.005"
    assert payload["h4_risk_pct"] == "0.002"
    assert "enable_reversal_probe" not in payload
    assert "pullback_zone_atr_multiplier" not in payload
    assert "require_pullback_close_beyond_fast_ma" not in payload


def test_batch_backtest_script_uses_weekly_daily_h4_terms_only():
    import scripts.run_strategy_backtest_batch as batch

    parameter_set = batch.ParameterSet(fast_period=15, slow_period=60)

    assert batch.SUPPORTED_INTERVALS == ("1w", "1d", "4h")
    assert "WEEKLY_DAILY_H4_V1" in parameter_set.label()
    assert "Reversal" not in parameter_set.label()
    assert "ZoneATR" not in parameter_set.label()
    assert "CloseBeyondMA" not in parameter_set.label()


def test_backtest_pages_show_new_kernel_not_old_layered_bucket_terms():
    from app.paper.web_status import render_strategy_backtest_batch_html, render_strategy_backtest_html

    backtest_html = render_strategy_backtest_html()
    batch_html = render_strategy_backtest_batch_html()
    combined = backtest_html + batch_html

    assert "WEEKLY_DAILY_H4_V1" in combined
    assert "1w 周线 + 1d 日线 + 4h 执行" in combined
    assert "Bucket" not in combined
    assert "分层策略" not in combined
    assert "Reversal" not in combined
    assert "趋势转换试仓" not in combined


def test_backtest_page_exposes_layered_risk_pct_inputs():
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html()

    assert 'name="weekly_risk_pct"' in html
    assert 'value="0.008"' in html
    assert 'name="daily_risk_pct"' in html
    assert 'value="0.005"' in html
    assert 'name="h4_risk_pct"' in html
    assert 'value="0.002"' in html
    assert "周线风险" in html
    assert "日线风险" in html
    assert "4H风险" in html


def test_backtest_query_parses_layered_risk_pct_inputs():
    from scripts.run_paper_status_web import _backtest_config_from_query

    config = _backtest_config_from_query(
        {
            "weekly_risk_pct": ["0.01"],
            "daily_risk_pct": ["0.006"],
            "h4_risk_pct": ["0.0025"],
        }
    )

    assert str(config.weekly_risk_pct) == "0.01"
    assert str(config.daily_risk_pct) == "0.006"
    assert str(config.h4_risk_pct) == "0.0025"


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


def test_runtime_events_cli_labels_bucket_as_position_level():
    from scripts.show_paper_runtime_events import format_paper_runtime_events

    assert "层级" in format_paper_runtime_events([])
