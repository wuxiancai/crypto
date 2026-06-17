from decimal import Decimal


def test_calculates_main_strategy_position_size_from_risk_budget():
    from app.risk.position_sizing import calculate_main_position_size

    result = calculate_main_position_size(
        account_equity=Decimal("10000"),
        risk_per_trade_pct=Decimal("0.01"),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        quantity_step=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=Decimal("5"),
    )

    assert result.quantity == Decimal("20.000")
    assert result.risk_amount == Decimal("100.00")
    assert result.notional == Decimal("2000.000")
    assert result.is_valid is True


def test_calculates_reversal_position_size_with_risk_and_score_caps():
    from app.risk.position_sizing import calculate_reversal_position_size

    result = calculate_reversal_position_size(
        account_equity=Decimal("10000"),
        standard_quantity=Decimal("20"),
        signal_level="EARLY",
        score=Decimal("80"),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        quantity_step=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=Decimal("5"),
    )

    assert result.quantity == Decimal("4.000")
    assert result.risk_amount == Decimal("20.000")
    assert result.notional == Decimal("400.000")
    assert result.is_valid is True
