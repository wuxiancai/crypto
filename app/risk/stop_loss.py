from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class StopCandidate:
    name: str
    price: Decimal


@dataclass(frozen=True)
class SelectedStopLoss:
    name: str
    price: Decimal
    distance_pct: Decimal


def select_stop_loss(
    side: str,
    entry_price: Decimal,
    candidates: Iterable[StopCandidate],
    max_stop_distance_pct: Decimal,
) -> SelectedStopLoss | None:
    valid_candidates = [
        SelectedStopLoss(
            name=candidate.name,
            price=candidate.price,
            distance_pct=_distance_pct(side, entry_price, candidate.price),
        )
        for candidate in candidates
        if _is_directionally_valid(side, entry_price, candidate.price)
    ]
    allowed_candidates = [
        candidate
        for candidate in valid_candidates
        if candidate.distance_pct <= max_stop_distance_pct
    ]
    if not allowed_candidates:
        return None
    return min(allowed_candidates, key=lambda candidate: candidate.distance_pct)


def _is_directionally_valid(side: str, entry_price: Decimal, stop_price: Decimal) -> bool:
    if side == "LONG":
        return stop_price < entry_price
    if side == "SHORT":
        return stop_price > entry_price
    raise ValueError(f"unsupported side: {side}")


def _distance_pct(side: str, entry_price: Decimal, stop_price: Decimal) -> Decimal:
    if side == "LONG":
        return (entry_price - stop_price) / entry_price
    if side == "SHORT":
        return (stop_price - entry_price) / entry_price
    raise ValueError(f"unsupported side: {side}")
