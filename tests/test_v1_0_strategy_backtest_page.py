import json
from decimal import Decimal


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
            config=StrategyBacktestConfig(
                fast_ma_type="EMA",
                slow_ma_type="MA",
                ema_fast_period=30,
                ema_slow_period=120,
                limit=300,
            ),
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
    assert "快线类型" in html
    assert 'name="fast_ma_type"' in html
    assert '<option value="EMA" selected>EMA</option>' in html
    assert "快线周期" in html
    assert 'name="ema_fast"' in html
    assert 'value="30"' in html
    assert "慢线类型" in html
    assert 'name="slow_ma_type"' in html
    assert '<option value="MA" selected>MA</option>' in html
    assert "慢线周期" in html
    assert 'name="ema_slow"' in html
    assert 'value="120"' in html
    assert "历史K线根数" in html
    assert "手续费/风险上限" in html
    assert 'name="max_fee_to_risk_ratio"' in html
    assert 'value="0.25"' in html
    assert "账户权益 USDT" in html
    assert "1030.25" in html
    assert "总交易次数" in html
    assert "胜 / 负 / 胜率" in html
    assert "1 / 1 / 胜率 50%" in html
    assert "BTCUSDT" in html
    assert "策略K线图" not in html
    assert "持仓情况" not in html


def test_strategy_backtest_defaults_to_binance_single_request_limit():
    from app.paper.strategy_backtest import StrategyBacktestConfig
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html()

    assert StrategyBacktestConfig().symbols == ("BTCUSDT",)
    assert StrategyBacktestConfig().limit == 1500
    assert 'name="limit"' in html
    assert 'value="1500"' in html


def test_strategy_backtest_page_selects_one_symbol_and_uses_compact_form():
    from app.paper.strategy_backtest import StrategyBacktestConfig, StrategyBacktestResult
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html(
        result=StrategyBacktestResult(
            config=StrategyBacktestConfig(symbols=("ETHUSDT",)),
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

    assert "交易对" in html
    assert 'name="symbol"' in html
    assert '<option value="BTCUSDT">BTC</option>' in html
    assert '<option value="ETHUSDT" selected>ETH</option>' in html
    assert "grid-template-columns: 100px 95px 95px 95px 130px 145px 145px 130px" in html


def test_strategy_backtest_query_uses_selected_single_symbol_and_ma_types():
    from scripts.run_paper_status_web import _backtest_config_from_query

    config = _backtest_config_from_query(
        {
            "symbol": ["ETHUSDT"],
            "run": ["1"],
            "fast_ma_type": ["EMA"],
            "slow_ma_type": ["MA"],
            "max_fee_to_risk_ratio": ["0.25"],
        }
    )

    assert config.symbols == ("ETHUSDT",)
    assert config.fast_ma_type == "EMA"
    assert config.slow_ma_type == "MA"
    assert config.max_fee_to_risk_ratio == Decimal("0.25")


def test_strategy_backtest_web_helper_archives_successful_result():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session, sessionmaker

    from app.database.models import BacktestRun, BacktestTradeRecord, Base, ConfigSnapshot
    from app.database.repositories import list_strategy_backtest_summaries
    from app.paper.strategy_backtest import StrategyBacktestConfig, StrategyBacktestResult
    from scripts.run_paper_status_web import _archive_strategy_backtest_result

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    result = StrategyBacktestResult(
        config=StrategyBacktestConfig(
            symbols=("BTCUSDT",),
            fast_ma_type="EMA",
            slow_ma_type="MA",
            ema_fast_period=30,
            ema_slow_period=120,
        ),
        initial_equity="1000.00",
        final_equity="1019.00",
        total_trades=1,
        wins=1,
        losses=0,
        net_pnl="19.00",
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

    archived = _archive_strategy_backtest_result(result, session_factory=session_factory)

    with Session(engine) as session:
        saved_run = session.execute(select(BacktestRun)).scalar_one()
        saved_trade = session.execute(select(BacktestTradeRecord)).scalar_one()
        saved_config = session.execute(select(ConfigSnapshot)).scalar_one()
        summaries = list_strategy_backtest_summaries(session)

    assert archived.error is None
    assert saved_run.final_equity == Decimal("1019.00")
    assert saved_trade.net_pnl == Decimal("19")
    assert saved_config.name == "strategy_backtest"
    config_payload = json.loads(saved_config.content)
    assert config_payload["fast_ma_type"] == "EMA"
    assert config_payload["slow_ma_type"] == "MA"
    assert summaries[0].symbol == "BTCUSDT"
    assert summaries[0].fast_ma_type == "EMA"
    assert summaries[0].slow_ma_type == "MA"
    assert summaries[0].final_equity == "1019.00"


def test_strategy_backtest_page_shows_recent_results_newest_first():
    from datetime import datetime, timezone

    from app.paper.strategy_backtest import StrategyBacktestRunSummary
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html(
        recent_results=[
            StrategyBacktestRunSummary(
                created_at=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
                symbol="ETHUSDT",
                fast_ma_type="MA",
                fast_period=30,
                slow_ma_type="EMA",
                slow_period=120,
                history_period="6m",
                initial_equity="1000.00",
                final_equity="980.00",
                total_trades=10,
                wins=4,
                losses=6,
                net_pnl="-20.00",
            ),
            StrategyBacktestRunSummary(
                created_at=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
                symbol="BTCUSDT",
                fast_ma_type="EMA",
                fast_period=50,
                slow_ma_type="MA",
                slow_period=200,
                history_period="1y",
                initial_equity="1000.00",
                final_equity="1044.00",
                total_trades=25,
                wins=11,
                losses=14,
                net_pnl="44.00",
            ),
        ]
    )

    assert "最近回测结果" in html
    assert "recent-results-scroll" in html
    assert "EMA50 / MA200" in html
    assert "11 / 14 / 胜率 44%" in html
    assert html.index("BTCUSDT") < html.index("ETHUSDT")


def test_strategy_backtest_page_links_to_batch_parameter_page():
    from app.paper.web_status import render_strategy_backtest_html

    html = render_strategy_backtest_html()

    assert "批量参数回测" in html
    assert 'href="/backtest/batch"' in html
    assert 'target="_blank"' in html


def test_strategy_backtest_batch_page_shows_all_script_parameters():
    from app.paper.web_status import render_strategy_backtest_batch_html
    from scripts.run_strategy_backtest_batch import StrategyBacktestBatchConfig

    html = render_strategy_backtest_batch_html(
        config=StrategyBacktestBatchConfig(
            symbol="ETHUSDT",
            fast_ma_type="EMA",
            slow_ma_type="MA",
            fast_periods=(15, 20, 25),
            slow_periods=(60, 90, 120),
            atr_periods=(10, 14),
            dmi_periods=(12, 16),
            swing_lookbacks=(15, 20),
            max_fee_to_risk_ratios=("0.20", "0.25"),
            take_profit_modes=("TRAILING", "FIXED"),
            history_period="6m",
        )
    )

    assert "批量参数回测" in html
    assert 'name="fast_start"' in html
    assert 'value="15"' in html
    assert 'name="fast_step"' in html
    assert 'value="5"' in html
    assert 'name="slow_start"' in html
    assert 'value="60"' in html
    assert 'name="slow_step"' in html
    assert "ATR 周期" in html
    assert 'name="atr_periods"' in html
    assert 'value="10,14"' in html
    assert "DMI 周期" in html
    assert "Swing Lookback" in html
    assert "手续费/风险上限" in html
    assert "止盈模式" in html
    assert "回测周期" in html
    assert "开始批量回测" in html


def test_strategy_backtest_web_helper_reports_runner_errors(monkeypatch):
    import scripts.run_paper_status_web as web

    async def fail_backtest(config):
        raise TimeoutError("connect timed out")

    monkeypatch.setattr(web, "run_strategy_backtest", fail_backtest)

    result = web._run_strategy_backtest_from_query({"symbol": ["BTCUSDT"], "history_period": ["3m"]})

    assert result.total_trades == 0
    assert result.error == "回测执行失败：connect timed out"


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
