from decimal import Decimal


def test_selects_closest_valid_long_stop_loss_candidate():
    from app.risk.stop_loss import StopCandidate, select_stop_loss

    result = select_stop_loss(
        side="LONG",
        entry_price=Decimal("100"),
        candidates=[
            StopCandidate(name="swing_low", price=Decimal("94")),
            StopCandidate(name="ema200", price=Decimal("96")),
            StopCandidate(name="atr", price=Decimal("97")),
            StopCandidate(name="invalid_above_entry", price=Decimal("101")),
        ],
        max_stop_distance_pct=Decimal("0.08"),
    )

    assert result.name == "atr"
    assert result.price == Decimal("97")
    assert result.distance_pct == Decimal("0.03")


def test_selects_closest_valid_short_stop_loss_candidate():
    from app.risk.stop_loss import StopCandidate, select_stop_loss

    result = select_stop_loss(
        side="SHORT",
        entry_price=Decimal("100"),
        candidates=[
            StopCandidate(name="swing_high", price=Decimal("106")),
            StopCandidate(name="ema200", price=Decimal("104")),
            StopCandidate(name="atr", price=Decimal("103")),
            StopCandidate(name="invalid_below_entry", price=Decimal("99")),
        ],
        max_stop_distance_pct=Decimal("0.08"),
    )

    assert result.name == "atr"
    assert result.price == Decimal("103")
    assert result.distance_pct == Decimal("0.03")


def test_rejects_stop_loss_when_all_candidates_are_too_far():
    from app.risk.stop_loss import StopCandidate, select_stop_loss

    result = select_stop_loss(
        side="LONG",
        entry_price=Decimal("100"),
        candidates=[
            StopCandidate(name="wide_swing", price=Decimal("80")),
            StopCandidate(name="wide_atr", price=Decimal("85")),
        ],
        max_stop_distance_pct=Decimal("0.08"),
    )

    assert result is None
