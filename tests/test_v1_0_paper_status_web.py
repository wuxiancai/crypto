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
