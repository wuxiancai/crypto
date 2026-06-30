def test_strategy_backtest_config_payload_uses_weekly_daily_h4_kernel():
    from app.database.repositories import strategy_backtest_config_payload
    from app.paper.strategy_backtest import StrategyBacktestConfig

    payload = strategy_backtest_config_payload(StrategyBacktestConfig())

    assert payload["strategy_kernel"] == "WEEKLY_DAILY_H4_V1"
    assert payload["timeframes"] == "1w,1d,4h"
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


def test_runtime_events_cli_labels_bucket_as_position_level():
    from scripts.show_paper_runtime_events import format_paper_runtime_events

    assert "层级" in format_paper_runtime_events([])
