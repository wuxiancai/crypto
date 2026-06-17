from decimal import Decimal


def test_liquidation_guard_accepts_long_when_stop_is_above_liquidation_buffer():
    from app.execution.liquidation_guard import evaluate_liquidation_guard

    result = evaluate_liquidation_guard(
        side="LONG",
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        estimated_liquidation_price=Decimal("90"),
        liquidation_buffer_pct=Decimal("0.01"),
    )

    assert result.is_safe is True
    assert result.reasons == ()


def test_liquidation_guard_rejects_long_when_stop_is_too_close_to_liquidation():
    from app.execution.liquidation_guard import evaluate_liquidation_guard

    result = evaluate_liquidation_guard(
        side="LONG",
        entry_price=Decimal("100"),
        stop_loss=Decimal("90.5"),
        estimated_liquidation_price=Decimal("90"),
        liquidation_buffer_pct=Decimal("0.01"),
    )

    assert result.is_safe is False
    assert result.reasons == ("stop_too_close_to_liquidation",)


def test_liquidation_guard_accepts_short_when_stop_is_below_liquidation_buffer():
    from app.execution.liquidation_guard import evaluate_liquidation_guard

    result = evaluate_liquidation_guard(
        side="SHORT",
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        estimated_liquidation_price=Decimal("110"),
        liquidation_buffer_pct=Decimal("0.01"),
    )

    assert result.is_safe is True
    assert result.reasons == ()


def test_liquidation_guard_rejects_short_when_prices_are_in_wrong_order():
    from app.execution.liquidation_guard import evaluate_liquidation_guard

    result = evaluate_liquidation_guard(
        side="SHORT",
        entry_price=Decimal("100"),
        stop_loss=Decimal("111"),
        estimated_liquidation_price=Decimal("110"),
        liquidation_buffer_pct=Decimal("0.01"),
    )

    assert result.is_safe is False
    assert result.reasons == ("invalid_price_order",)
