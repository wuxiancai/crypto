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
    assert "全部模拟交易记录" in html
    assert "买入价" in html
    assert "卖出价" in html
    assert "使用策略" in html
    assert "ETHUSDT" in html
    assert "做空" in html
    assert "BTCUSDT" in html
    assert "REVERSAL_PROBE" in html
    assert "止盈" in html
    assert "止损" in html
    assert "rejected-signals" in html


def test_fill_prices_are_displayed_as_buy_and_sell_prices_for_long_and_short(tmp_path):
    from app.paper.web_status import build_paper_status_payload, render_paper_status_html

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [
                    {
                        "symbol": "BTCUSDT",
                        "side": "LONG",
                        "strategy_type": "TREND_PULLBACK",
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
                        "strategy_type": "REVERSAL_PROBE",
                        "entry_time": 3,
                        "exit_time": 4,
                        "entry_price": "1800",
                        "exit_price": "1760",
                        "quantity": "0.2",
                        "gross_pnl": "8",
                        "fees": "0.1",
                        "net_pnl": "7.9",
                        "exit_reason": "TAKE_PROFIT",
                    },
                ],
                "rejected_signals": 0,
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "64000" in html
    assert "64600" in html
    assert "1760" in html
    assert "1800" in html


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

    assert "最近策略输出" in html
    assert "BTCUSDT" in html
    assert "15m" in html
    assert "等待" in html
    assert "TREND_PULLBACK" in html
    assert "price not in ema50 pullback zone" in html


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

    assert "最近策略输出" in html
    assert html.count("<tr>") >= 3
    assert "15m" in html
    assert "5m" in html
    assert "策略K线图" in html
    assert "EMA50" in html
    assert "EMA200" in html
    assert "4h EMA200 &gt; EMA50：空头基础" in html
    assert "<svg" in html


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
    assert "即将触发：主趋势做空（5/6）" in html
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

    assert "当前趋势：主趋势做空" in html
    assert "已满足 3/6" in html
    assert "还差：4h 下跌趋势、1h 下跌趋势、15m 反弹到 EMA50 区域" in html
    assert "主趋势做多" not in html
    assert "趋势转换做多" not in html
    assert "long detail should be hidden" not in html
    assert "reversal detail should be hidden" not in html
    assert "<summary>计算明细</summary>" in html
