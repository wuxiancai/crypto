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
            }
        ),
        encoding="utf-8",
    )

    html = render_paper_status_html(build_paper_status_payload(state_path))

    assert "10080" in html
    assert "ETHUSDT" in html
    assert "SHORT" in html
    assert "BTCUSDT" in html
    assert "REVERSAL_PROBE" in html
    assert "TAKE_PROFIT" in html
    assert "STOP_LOSS" in html
    assert "rejected-signals" in html
