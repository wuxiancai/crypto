import json


def test_paper_status_payload_marks_missing_state_file(tmp_path):
    from app.paper.web_status import build_paper_status_payload

    payload = build_paper_status_payload(tmp_path / "missing.json")

    assert payload["status"] == "WAITING_FOR_STATE"
    assert payload["equity"] is None
    assert payload["fills"] == []


def test_paper_status_html_shows_open_position_and_all_fills(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "10080",
                "open_position": {
                    "symbol": "ETHUSDT",
                    "side": "SHORT",
                    "strategy_type": "TREND_PULLBACK",
                    "entry_time": 1000,
                    "entry_price": "1800",
                    "stop_loss": "1820",
                    "take_profit": "1760",
                    "quantity": "0.5",
                    "entry_fee": "0.36",
                    "trailing_active": True,
                },
                "fills": [
                    {
                        "symbol": "BTCUSDT",
                        "side": "LONG",
                        "strategy_type": "REVERSAL_PROBE",
                        "entry_time": 1,
                        "exit_time": 2,
                        "entry_price": "64000",
                        "exit_price": "64600",
                        "quantity": "0.01",
                        "gross_pnl": "6",
                        "fees": "0.2",
                        "net_pnl": "5.8",
                        "exit_reason": "TAKE_PROFIT",
                    },
                    {
                        "symbol": "ETHUSDT",
                        "side": "SHORT",
                        "strategy_type": "TREND_PULLBACK",
                        "entry_time": 3,
                        "exit_time": 4,
                        "entry_price": "1800",
                        "exit_price": "1810",
                        "quantity": "0.2",
                        "gross_pnl": "-2",
                        "fees": "0.1",
                        "net_pnl": "-2.1",
                        "exit_reason": "STOP_LOSS",
                    },
                ],
                "rejected_signals": 1,
                "runtime_started_at_ms": 1_000,
                "last_update_at_ms": 121_000,
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path, current_time_ms=121_000))

    assert "10080" in html
    assert "模拟交易看板" in html
    assert "系统运行时间" in html
    assert "2 分钟" in html
    assert "账户权益" in html
    assert "持仓情况" in html
    assert "移动止盈中" in html
    assert "全部模拟交易记录" in html
    assert "开仓时间 UTC+8" in html
    assert "平仓时间 UTC+8" in html
    assert "开仓价" in html
    assert "平仓价" in html
    assert "手续费" in html
    assert "资金费" in html
    assert "使用策略" in html
    assert "ETHUSDT" in html
    assert "做空" in html
    assert "BTCUSDT" in html
    assert "REVERSAL_PROBE" in html
    assert "止盈" in html
    assert "止损" in html
    assert "rejected-signals" in html


def test_status_page_formats_numbers_times_and_compact_trade_list(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    fills = []
    for index in range(6):
        fills.append(
            {
                "symbol": "BTCUSDT",
                "side": "SHORT",
                "strategy_type": "TREND_PULLBACK",
                "entry_time": 1_800_000 + index,
                "exit_time": 2_700_000 + index,
                "entry_price": "62847.007800",
                "exit_price": "62959.704400",
                "quantity": "0.04380682621021708124083866467",
                "gross_pnl": "-4.936880370682350317766298657",
                "fees": "1.653851521264327346788839261",
                "funding_fee": "0.200000",
                "net_pnl": "-6.590731891946677664555137918",
                "exit_reason": "STOP_LOSS",
                "exit_detail": "做空止损：最高价触达止损价 62959.704400",
            }
        )
    state_path.write_text(
        json.dumps(
            {
                "equity": "1059.420713783168846837195651",
                "open_position": {
                    "symbol": "BTCUSDT",
                    "side": "SHORT",
                    "strategy_type": "TREND_PULLBACK",
                    "entry_time": 1_000,
                    "entry_price": "62908.530000",
                    "stop_loss": "63079.00",
                    "take_profit": "62662.00",
                    "quantity": "0.03107352360483278133505002789",
                    "entry_fee": "0",
                },
                "fills": fills,
                "rejected_signals": 0,
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "1059.42" in html
    assert "62908.53" in html
    assert "0.0311" in html
    assert "62847.01" in html
    assert "62959.70" in html
    assert "-6.59" in html
    assert "1.65" in html
    assert "0.20" in html
    assert "做空止损：最高价触达止损价 62959.70" in html
    assert "1970-01-01 08:30" in html
    assert "1970-01-01 08:45" in html
    assert "trade-scroll" in html
    assert html.find("2,700,005") < html.find("2,700,000")


def test_status_page_uses_soft_refresh_without_full_page_meta_reload(tmp_path):
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

    assert '<meta http-equiv="refresh"' not in html
    assert "5 秒自动刷新" in html
    assert "setInterval(refreshDashboard, 5000)" in html
    assert "fetch(window.location.href" in html
    assert "snapshotActiveCharts" in html
    assert "restoreActiveCharts" in html


def test_paper_status_page_shows_only_error_log_lines_in_red(tmp_path):
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
    log_path = tmp_path / "paper-realtime.log"
    log_path.write_text(
        "\n".join(
            [
                "Paper runner started",
                "Historical warmup skipped for BTCUSDT 4h: Binance futures data endpoint returned HTTP 451",
                "ERROR websocket disconnected",
            ]
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(
        build_paper_status_payload(state_path, error_log_path=log_path)
    )

    assert "错误日志" in html
    assert "Historical warmup skipped" in html
    assert "ERROR websocket disconnected" in html
    assert "Paper runner started" not in html
    assert "error-log-line" in html
    assert "color: #b42318" in html


def test_paper_status_page_summarizes_tracebacks_in_error_log(tmp_path):
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
    log_path = tmp_path / "paper-realtime.log"
    log_path.write_text(
        "\n".join(
            [
                "Traceback (most recent call last):",
                '  File "/home/wuxiancai/crypto/.venv/lib/python3.12/site-packages/httpx/_transports/default.py", line 101, in map_httpcore_exceptions',
                "    with map_exceptions(exc_map):",
                "httpcore.ConnectTimeout",
                "The above exception was the direct cause of the following exception:",
                "Traceback (most recent call last):",
                "httpx.ConnectTimeout",
            ]
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(
        build_paper_status_payload(state_path, error_log_path=log_path)
    )

    assert "Binance REST 连接超时" in html
    assert "Traceback" not in html
    assert "map_httpcore_exceptions" not in html
    assert "The above exception" not in html


def test_paper_status_page_shows_recent_strategy_outputs(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "signal_evaluations": [
                    {
                        "evaluated_at_ms": 1_800_000,
                        "symbol": "BTCUSDT",
                        "interval": "15m",
                        "close": "64000",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "reason": ["price not in ema50 pullback zone"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "最近策略输出" not in html
    assert "price not in ema50 pullback zone" not in html


def test_paper_status_page_explains_missing_strategy_data_and_shows_price_ticker(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1144.17",
                "open_position": {
                    "symbol": "BTCUSDT",
                    "side": "SHORT",
                    "strategy_type": "TREND_PULLBACK",
                    "entry_time": 1_000,
                    "entry_price": "62594.79",
                    "stop_loss": "62896.80",
                    "take_profit": "62084.70",
                    "quantity": "0.0189",
                    "entry_fee": "0",
                },
                "fills": [
                    {
                        "symbol": "ETHUSDT",
                        "side": "SHORT",
                        "strategy_type": "TREND_PULLBACK",
                        "entry_time": 1,
                        "exit_time": 2,
                        "entry_price": "1705.20",
                        "exit_price": "1688.40",
                        "quantity": "0.1",
                        "gross_pnl": "1.68",
                        "fees": "0.1",
                        "funding_fee": "0",
                        "net_pnl": "1.58",
                        "exit_reason": "TAKE_PROFIT",
                    }
                ],
                "rejected_signals": 0,
                "signal_evaluations": [],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "永续最新价" in html
    assert "BTCUSDT" in html
    assert "62594.79" in html
    assert "ETHUSDT" in html
    assert "1688.40" in html
    assert "暂无策略触发条件：等待实时策略评估更新" in html
    assert "暂无K线图数据：等待实时策略评估更新" in html


def test_paper_status_page_shows_latest_output_per_symbol_interval_and_chart(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "signal_evaluations": [
                    {
                        "evaluated_at_ms": 1,
                        "symbol": "BTCUSDT",
                        "interval": "15m",
                        "close": "64000",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "reason": ["price not in ema50 pullback zone"],
                        "core_rules": ["4h EMA200 > EMA50：空头基础"],
                        "chart_points": [
                            {
                                "open_time": 1,
                                "open": "63800",
                                "high": "64200",
                                "low": "63700",
                                "close": "64000",
                                "ema50": "63900",
                                "ema200": "64100",
                            },
                            {
                                "open_time": 2,
                                "open": "64000",
                                "high": "64300",
                                "low": "63900",
                                "close": "64100",
                                "ema50": "63950",
                                "ema200": "64090",
                            },
                        ],
                    },
                    {
                        "evaluated_at_ms": 2,
                        "symbol": "BTCUSDT",
                        "interval": "5m",
                        "close": "64120",
                        "action": "WAIT",
                        "strategy_type": "SYSTEM",
                        "reason": ["non-strategy interval observed"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "最近策略输出" not in html
    assert "non-strategy interval observed" not in html
    assert "策略K线图" in html
    assert "EMA50" in html
    assert "EMA200" in html
    assert "4h EMA200 &gt; EMA50：空头基础" in html
    assert "<svg" in html


def test_paper_status_page_hides_recent_strategy_output_table_from_main_dashboard(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "signal_evaluations": [
                    {
                        "evaluated_at_ms": 1,
                        "symbol": "BTCUSDT",
                        "interval": "5m",
                        "close": "63264.40",
                        "action": "WAIT",
                        "strategy_type": "SYSTEM",
                        "reason": ["no actionable signal"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "最近策略输出" not in html
    assert "no actionable signal" not in html


def test_paper_status_page_can_switch_strategy_chart_timeframes(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    point = {
        "open_time": 1,
        "open": "100",
        "high": "110",
        "low": "95",
        "close": "105",
        "ema50": "103",
        "ema200": "101",
    }
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "signal_evaluations": [
                    {
                        "evaluated_at_ms": 1,
                        "symbol": "BTCUSDT",
                        "interval": "15m",
                        "close": "105",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "reason": ["no actionable signal"],
                        "core_rules": ["4h EMA50 > EMA200：多头基础"],
                        "chart_timeframes": {
                            "4h": [point, {**point, "open_time": 2, "close": "106"}],
                            "1h": [point, {**point, "open_time": 2, "close": "104"}],
                            "15m": [point, {**point, "open_time": 2, "close": "103"}],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert 'data-chart-target="chart-4h"' in html
    assert 'data-chart-target="chart-1h"' in html
    assert 'data-chart-target="chart-15m"' in html
    assert 'data-chart-panel="chart-4h"' in html
    assert 'data-chart-panel="chart-1h"' in html
    assert 'data-chart-panel="chart-15m"' in html
    assert ">4h<" in html
    assert ">1h<" in html
    assert ">15m<" in html


def test_paper_status_page_can_switch_strategy_chart_symbols_and_compacts_rules(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    point = {
        "open_time": 1,
        "open": "100",
        "high": "110",
        "low": "95",
        "close": "105",
        "ema50": "103",
        "ema200": "101",
    }
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "signal_evaluations": [
                    {
                        "evaluated_at_ms": 1,
                        "symbol": "BTCUSDT",
                        "interval": "15m",
                        "close": "105",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "reason": ["no actionable signal"],
                        "core_rules": ["4h EMA200 > EMA50：空头基础", "1h EMA200 > EMA50：空头基础"],
                        "chart_timeframes": {
                            "4h": [point, {**point, "open_time": 2, "close": "106"}],
                            "1h": [point, {**point, "open_time": 2, "close": "104"}],
                            "15m": [point, {**point, "open_time": 2, "close": "103"}],
                        },
                    },
                    {
                        "evaluated_at_ms": 2,
                        "symbol": "ETHUSDT",
                        "interval": "15m",
                        "close": "205",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "reason": ["no actionable signal"],
                        "core_rules": ["4h EMA200 > EMA50：空头基础", "1h EMA50 > EMA200：多头基础"],
                        "chart_timeframes": {
                            "4h": [point, {**point, "open_time": 2, "close": "206"}],
                            "1h": [point, {**point, "open_time": 2, "close": "204"}],
                            "15m": [point, {**point, "open_time": 2, "close": "203"}],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert ".rule-list { display: flex;" in html
    assert 'data-chart-target="symbol-BTCUSDT"' in html
    assert 'data-chart-target="symbol-ETHUSDT"' in html
    assert 'data-chart-panel="symbol-BTCUSDT"' in html
    assert 'data-chart-panel="symbol-ETHUSDT"' in html
    assert 'data-chart-panel="chart-BTCUSDT-4h"' in html
    assert 'data-chart-panel="chart-ETHUSDT-4h"' in html
    assert "BTCUSDT · 4h" in html
    assert "ETHUSDT · 4h" in html


def test_paper_status_page_shows_strategy_trigger_conditions(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "signal_evaluations": [
                    {
                        "evaluated_at_ms": 1,
                        "symbol": "BTCUSDT",
                        "interval": "15m",
                        "close": "105",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "reason": ["price not in ema50 pullback zone"],
                        "nearest_strategy": {
                            "name": "主趋势做空",
                            "matched": 5,
                            "total": 6,
                            "action": "SHORT_ENTRY",
                        },
                        "condition_statuses": [
                            {
                                "strategy": "主趋势做空",
                                "text": "4h 下跌趋势",
                                "passed": True,
                                "detail": "close < EMA200",
                            },
                            {
                                "strategy": "主趋势做空",
                                "text": "15m 看跌确认",
                                "passed": False,
                                "detail": "close >= previous_close",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "策略触发条件" in html
    assert "当前趋势：BTCUSDT 主趋势做空 · 已满足 5/6" in html
    assert "还差：15m 看跌确认" in html
    assert "4h 下跌趋势" in html
    assert "15m 看跌确认" in html
    assert "close &lt; EMA200" in html
    assert "close &gt;= previous_close" in html
    assert "condition-pass" in html
    assert "condition-fail" in html


def test_paper_status_page_shows_only_nearest_strategy_conditions_in_compact_view(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "signal_evaluations": [
                    {
                        "evaluated_at_ms": 1,
                        "symbol": "ETHUSDT",
                        "interval": "15m",
                        "close": "1723",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "reason": ["missing bearish 15m confirmation"],
                        "nearest_strategy": {
                            "name": "主趋势做空",
                            "matched": 3,
                            "total": 6,
                            "action": "SHORT_ENTRY",
                        },
                        "condition_statuses": [
                            {
                                "strategy": "主趋势做多",
                                "text": "4h 上涨趋势",
                                "passed": False,
                                "detail": "long detail should be hidden",
                            },
                            {
                                "strategy": "主趋势做空",
                                "text": "4h 下跌趋势",
                                "passed": False,
                                "detail": "close < EMA200",
                            },
                            {
                                "strategy": "主趋势做空",
                                "text": "1h 下跌趋势",
                                "passed": False,
                                "detail": "close < EMA200",
                            },
                            {
                                "strategy": "主趋势做空",
                                "text": "15m 反弹到 EMA50 区域",
                                "passed": False,
                                "detail": "|close-EMA50| <= ATR",
                            },
                            {
                                "strategy": "主趋势做空",
                                "text": "15m 看跌确认",
                                "passed": True,
                                "detail": "close < previous_close",
                            },
                            {
                                "strategy": "主趋势做空",
                                "text": "止损有效",
                                "passed": True,
                                "detail": "entry < swing_high",
                            },
                            {
                                "strategy": "主趋势做空",
                                "text": "风险收益比达标",
                                "passed": True,
                                "detail": "RR >= 1.5",
                            },
                            {
                                "strategy": "趋势转换做多",
                                "text": "评分达到 70",
                                "passed": False,
                                "detail": "reversal detail should be hidden",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "当前趋势：ETHUSDT 主趋势做空" in html
    assert "已满足 3/6" in html
    assert "还差：4h 下跌趋势、1h 下跌趋势、15m 反弹到 EMA50 区域" in html
    assert "主趋势做多" not in html
    assert "趋势转换做多" not in html
    assert "long detail should be hidden" not in html
    assert "reversal detail should be hidden" not in html
    assert "<summary>计算明细</summary>" in html


def test_paper_status_page_shows_strategy_conditions_for_each_symbol(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "signal_evaluations": [
                    {
                        "evaluated_at_ms": 1,
                        "symbol": "BTCUSDT",
                        "interval": "15m",
                        "close": "62720",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "nearest_strategy": {
                            "name": "主趋势做空",
                            "matched": 6,
                            "total": 8,
                            "action": "SHORT_ENTRY",
                        },
                        "condition_statuses": [
                            {
                                "strategy": "主趋势做空",
                                "text": "4h 空头结构",
                                "passed": True,
                                "detail": "BTC bearish structure",
                            }
                        ],
                    },
                    {
                        "evaluated_at_ms": 2,
                        "symbol": "ETHUSDT",
                        "interval": "15m",
                        "close": "1720",
                        "action": "WAIT",
                        "strategy_type": "TREND_PULLBACK",
                        "nearest_strategy": {
                            "name": "主趋势做空",
                            "matched": 4,
                            "total": 8,
                            "action": "SHORT_ENTRY",
                        },
                        "condition_statuses": [
                            {
                                "strategy": "主趋势做空",
                                "text": "4h 空头结构",
                                "passed": False,
                                "detail": "ETH not below EMA50",
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "当前趋势：BTCUSDT 主趋势做空 · 已满足 6/8" in html
    assert "当前趋势：ETHUSDT 主趋势做空 · 已满足 4/8" in html
    assert "BTC bearish structure" in html
    assert "ETH not below EMA50" in html
    assert "condition-cards" in html
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in html
