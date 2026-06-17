from decimal import Decimal


def test_funding_filter_allows_normal_rate_outside_settlement_window():
    from app.risk.funding_filter import evaluate_funding_filter

    result = evaluate_funding_filter(
        funding_rate=Decimal("0.0002"),
        minutes_to_settlement=30,
    )

    assert result.decision == "ALLOW"
    assert result.position_multiplier == Decimal("1")
    assert result.reasons == ()


def test_funding_filter_warns_and_halves_position_when_rate_reaches_warn_threshold():
    from app.risk.funding_filter import evaluate_funding_filter

    result = evaluate_funding_filter(
        funding_rate=Decimal("-0.0005"),
        minutes_to_settlement=30,
    )

    assert result.decision == "WARN"
    assert result.position_multiplier == Decimal("0.5")
    assert result.reasons == ("funding_rate_warn",)


def test_funding_filter_blocks_when_rate_reaches_block_threshold():
    from app.risk.funding_filter import evaluate_funding_filter

    result = evaluate_funding_filter(
        funding_rate=Decimal("0.0015"),
        minutes_to_settlement=30,
    )

    assert result.decision == "BLOCK"
    assert result.position_multiplier == Decimal("0")
    assert result.reasons == ("funding_rate_block",)


def test_funding_filter_blocks_new_entries_near_settlement():
    from app.risk.funding_filter import evaluate_funding_filter

    result = evaluate_funding_filter(
        funding_rate=Decimal("0.0001"),
        minutes_to_settlement=15,
    )

    assert result.decision == "BLOCK"
    assert result.position_multiplier == Decimal("0")
    assert result.reasons == ("funding_settlement_window",)
