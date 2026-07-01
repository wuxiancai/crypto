def test_position_table_shows_timeline_policy_budget_label():
    from app.paper.web_status import _render_positions

    html = _render_positions(
        [
            {
                "symbol": "BTCUSDT",
                "side": "LONG",
                "strategy_type": "DAILY_LONG_REBOUND",
                "strategy_kernel": "WEEKLY_DAILY_H4_V1",
                "position_level": "DAILY",
                "trade_mode": "REBOUND",
                "entry_price": "100",
                "initial_stop_loss": "90",
                "stop_loss": "90",
                "take_profit": "120",
                "quantity": "1",
                "leverage": "5",
            }
        ]
    )

    assert "结构/预算" in html
    assert "反弹单：结构风险较高 / 风险预算较低" in html


def test_trade_identity_label_shows_main_direction_budget_label():
    from app.paper.web_status import _trade_identity_label

    html = _trade_identity_label(
        {
            "strategy_type": "H4_SHORT_CONTINUATION",
            "strategy_kernel": "WEEKLY_DAILY_H4_V1",
            "position_level": "H4",
            "trade_mode": "CONTINUATION",
        }
    )

    assert "主方向单：结构风险较低 / 风险预算较高" in html
