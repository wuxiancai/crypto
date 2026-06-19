import json


def test_status_page_links_to_strategy_backtest(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "策略回测" in html
    assert 'href="/backtest"' in html
    assert 'target="_blank"' in html


def test_strategy_backtest_page_shows_parameter_form_and_results():
    from app.paper.strategy_backtest import StrategyBacktestConfig, StrategyBacktestResult
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html(
        result=StrategyBacktestResult(
            config=StrategyBacktestConfig(ema_fast_period=30, ema_slow_period=120, limit=300),
            initial_equity="1000",
            final_equity="1030.25",
            total_trades=2,
            wins=1,
            losses=1,
            net_pnl="30.25",
            trades=[
                {
                    "symbol": "BTCUSDT",
                    "side": "SHORT",
                    "strategy_type": "TREND_PULLBACK",
                    "entry_time": 1_800_000,
                    "exit_time": 2_700_000,
                    "entry_price": "62847.0078",
                    "exit_price": "62223",
                    "quantity": "0.0167",
                    "net_pnl": "8.22",
                    "exit_reason": "TAKE_PROFIT",
                }
            ],
            error=None,
        )
    )

    assert "策略回测" in html
    assert "EMA 快线" in html
    assert 'name="ema_fast"' in html
    assert 'value="30"' in html
    assert "EMA 慢线" in html
    assert 'name="ema_slow"' in html
    assert 'value="120"' in html
    assert "历史K线根数" in html
    assert "账户权益 USDT" in html
    assert "1030.25" in html
    assert "总交易次数" in html
    assert "BTCUSDT" in html
    assert "策略K线图" not in html
    assert "持仓情况" not in html


def test_strategy_backtest_defaults_to_binance_single_request_limit():
    from app.paper.strategy_backtest import StrategyBacktestConfig
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html()

    assert StrategyBacktestConfig().limit == 1500
    assert 'name="limit"' in html
    assert 'value="1500"' in html


def test_strategy_backtest_page_supports_long_history_periods():
    from app.paper.strategy_backtest import StrategyBacktestConfig, StrategyBacktestResult
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html(
        result=StrategyBacktestResult(
            config=StrategyBacktestConfig(history_period="2y"),
            initial_equity="1000",
            final_equity="1000",
            total_trades=0,
            wins=0,
            losses=0,
            net_pnl="0",
            trades=[],
            error=None,
        )
    )

    assert "回测周期" in html
    assert 'name="history_period"' in html
    assert "最近3个月" in html
    assert "最近6个月" in html
    assert "最近1年" in html
    assert "最近2年" in html
    assert '<option value="2y" selected>' in html


def test_strategy_backtest_page_can_show_error_without_results():
    from app.paper.strategy_backtest import StrategyBacktestConfig, StrategyBacktestResult
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html(
        result=StrategyBacktestResult(
            config=StrategyBacktestConfig(),
            initial_equity="1000",
            final_equity="1000",
            total_trades=0,
            wins=0,
            losses=0,
            net_pnl="0",
            trades=[],
            error="无法访问 Binance REST",
        )
    )

    assert "无法访问 Binance REST" in html
    assert "暂无回测成交" in html
