from decimal import Decimal


def test_builds_order_plan_with_default_execution_constraints():
    from app.execution.order_plan import build_order_plan
    from app.risk.take_profit import TakeProfitLevel, TakeProfitPlan

    plan = build_order_plan(
        symbol="BTCUSDT",
        side="LONG",
        strategy_type="REVERSAL_PROBE",
        signal_id="sig-001",
        order_type="LIMIT",
        entry_price=Decimal("100"),
        quantity=Decimal("0.25"),
        stop_loss=Decimal("95"),
        take_profit_plan=TakeProfitPlan(
            levels=(
                TakeProfitLevel("TP1", Decimal("105"), Decimal("0.30")),
                TakeProfitLevel("TP2", Decimal("112"), Decimal("0.30")),
                TakeProfitLevel("TP3", Decimal("118"), Decimal("0.40")),
            ),
            move_stop_to_break_even_after="TP1",
        ),
        strategy_version="v0.5",
        config_snapshot_id="cfg-001",
        estimated_liquidation_price=Decimal("70"),
        liquidation_buffer_pct=Decimal("0.01"),
    )

    assert plan.position_mode == "ONE_WAY"
    assert plan.margin_type == "ISOLATED"
    assert plan.leverage == Decimal("10")
    assert plan.reduce_only is False
    assert plan.client_order_id == "REVERSAL_PROBE-sig-001-LONG"
    assert plan.take_profit_levels[0].price == Decimal("105")


def test_rejects_order_plan_when_requested_leverage_exceeds_max():
    from app.execution.order_plan import build_order_plan
    from app.risk.take_profit import TakeProfitPlan

    try:
        build_order_plan(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="TREND_PULLBACK",
            signal_id="sig-002",
            order_type="MARKET",
            entry_price=Decimal("100"),
            quantity=Decimal("0.1"),
            stop_loss=Decimal("95"),
            take_profit_plan=TakeProfitPlan(levels=(), move_stop_to_break_even_after="TP1"),
            strategy_version="v0.5",
            config_snapshot_id="cfg-001",
            estimated_liquidation_price=Decimal("70"),
            liquidation_buffer_pct=Decimal("0.01"),
            leverage=Decimal("12"),
            max_leverage=Decimal("10"),
        )
    except ValueError as exc:
        assert str(exc) == "leverage exceeds max_leverage"
    else:
        raise AssertionError("expected leverage validation error")
