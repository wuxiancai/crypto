from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class FundingFilterResult:
    decision: str
    position_multiplier: Decimal
    reasons: tuple[str, ...]


def evaluate_funding_filter(
    funding_rate: Decimal,
    minutes_to_settlement: int,
    warn_abs: Decimal = Decimal("0.0005"),
    block_abs: Decimal = Decimal("0.0015"),
    settlement_avoid_minutes: int = 15,
) -> FundingFilterResult:
    if minutes_to_settlement <= settlement_avoid_minutes:
        return FundingFilterResult(
            decision="BLOCK",
            position_multiplier=Decimal("0"),
            reasons=("funding_settlement_window",),
        )
    if abs(funding_rate) >= block_abs:
        return FundingFilterResult(
            decision="BLOCK",
            position_multiplier=Decimal("0"),
            reasons=("funding_rate_block",),
        )
    if abs(funding_rate) >= warn_abs:
        return FundingFilterResult(
            decision="WARN",
            position_multiplier=Decimal("0.5"),
            reasons=("funding_rate_warn",),
        )
    return FundingFilterResult(
        decision="ALLOW",
        position_multiplier=Decimal("1"),
        reasons=(),
    )
