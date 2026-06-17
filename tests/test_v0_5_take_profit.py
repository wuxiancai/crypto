from decimal import Decimal


def test_builds_long_reversal_take_profit_plan_with_valid_ema200_tp3():
    from app.risk.take_profit import build_reversal_take_profit_plan

    plan = build_reversal_take_profit_plan(
        side="LONG",
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        previous_high=Decimal("112"),
        previous_low=Decimal("90"),
        ema200_4h=Decimal("118"),
    )

    assert [(level.name, level.price, level.close_pct) for level in plan.levels] == [
        ("TP1", Decimal("105"), Decimal("0.30")),
        ("TP2", Decimal("112"), Decimal("0.30")),
        ("TP3", Decimal("118"), Decimal("0.40")),
    ]
    assert plan.move_stop_to_break_even_after == "TP1"


def test_long_reversal_tp3_falls_back_when_ema200_is_below_entry():
    from app.risk.take_profit import build_reversal_take_profit_plan

    plan = build_reversal_take_profit_plan(
        side="LONG",
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        previous_high=Decimal("112"),
        previous_low=Decimal("90"),
        ema200_4h=Decimal("98"),
    )

    assert plan.levels[2].price == Decimal("115")


def test_builds_short_reversal_take_profit_plan_with_valid_ema200_tp3():
    from app.risk.take_profit import build_reversal_take_profit_plan

    plan = build_reversal_take_profit_plan(
        side="SHORT",
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        previous_high=Decimal("110"),
        previous_low=Decimal("88"),
        ema200_4h=Decimal("82"),
    )

    assert [(level.name, level.price, level.close_pct) for level in plan.levels] == [
        ("TP1", Decimal("95"), Decimal("0.30")),
        ("TP2", Decimal("88"), Decimal("0.30")),
        ("TP3", Decimal("82"), Decimal("0.40")),
    ]
    assert plan.move_stop_to_break_even_after == "TP1"


def test_short_reversal_tp3_falls_back_when_ema200_is_above_entry():
    from app.risk.take_profit import build_reversal_take_profit_plan

    plan = build_reversal_take_profit_plan(
        side="SHORT",
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        previous_high=Decimal("110"),
        previous_low=Decimal("88"),
        ema200_4h=Decimal("102"),
    )

    assert plan.levels[2].price == Decimal("85")
