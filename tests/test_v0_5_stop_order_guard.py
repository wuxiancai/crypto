from decimal import Decimal


def test_stop_order_guard_accepts_valid_long_position_stop_order():
    from app.execution.stop_order_guard import PositionSnapshot, StopOrderSnapshot, evaluate_stop_order_guard

    result = evaluate_stop_order_guard(
        position=PositionSnapshot(symbol="BTCUSDT", side="LONG", quantity=Decimal("0.5"), entry_price=Decimal("100")),
        stop_orders=[
            StopOrderSnapshot(
                symbol="BTCUSDT",
                side="SELL",
                quantity=Decimal("0.5"),
                stop_price=Decimal("95"),
                reduce_only=True,
                status="NEW",
            )
        ],
    )

    assert result.is_protected is True
    assert result.action == "NONE"
    assert result.reasons == ()


def test_stop_order_guard_requires_reduce_only_quantity_coverage_and_correct_direction():
    from app.execution.stop_order_guard import PositionSnapshot, StopOrderSnapshot, evaluate_stop_order_guard

    result = evaluate_stop_order_guard(
        position=PositionSnapshot(symbol="ETHUSDT", side="SHORT", quantity=Decimal("1.2"), entry_price=Decimal("100")),
        stop_orders=[
            StopOrderSnapshot(
                symbol="ETHUSDT",
                side="SELL",
                quantity=Decimal("1.2"),
                stop_price=Decimal("105"),
                reduce_only=True,
                status="NEW",
            ),
            StopOrderSnapshot(
                symbol="ETHUSDT",
                side="BUY",
                quantity=Decimal("0.4"),
                stop_price=Decimal("105"),
                reduce_only=True,
                status="NEW",
            ),
            StopOrderSnapshot(
                symbol="ETHUSDT",
                side="BUY",
                quantity=Decimal("1.2"),
                stop_price=Decimal("105"),
                reduce_only=False,
                status="NEW",
            ),
        ],
    )

    assert result.is_protected is False
    assert result.action == "REPAIR_STOP_ORDER"
    assert result.reasons == ("missing_valid_stop_order",)


def test_stop_order_guard_rejects_trigger_price_on_wrong_side_of_entry():
    from app.execution.stop_order_guard import PositionSnapshot, StopOrderSnapshot, evaluate_stop_order_guard

    result = evaluate_stop_order_guard(
        position=PositionSnapshot(symbol="BTCUSDT", side="LONG", quantity=Decimal("0.5"), entry_price=Decimal("100")),
        stop_orders=[
            StopOrderSnapshot(
                symbol="BTCUSDT",
                side="SELL",
                quantity=Decimal("0.5"),
                stop_price=Decimal("101"),
                reduce_only=True,
                status="NEW",
            )
        ],
    )

    assert result.is_protected is False
    assert result.action == "REPAIR_STOP_ORDER"
    assert result.reasons == ("missing_valid_stop_order",)
