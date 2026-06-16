from dataclasses import dataclass
from decimal import Decimal

from app.strategy.trend_detector import TrendResult


@dataclass(frozen=True)
class ReversalSetup:
    entry_price: Decimal
    ema50_15m: Decimal
    atr_15m: Decimal
    four_hour_no_new_low: bool = False
    four_hour_no_new_high: bool = False
    four_hour_stop_structure: bool = False
    four_hour_exhaustion_structure: bool = False
    four_hour_near_or_above_ema50: bool = False
    four_hour_near_or_below_ema50: bool = False
    one_hour_close_above_ema50: bool = False
    one_hour_close_below_ema50: bool = False
    one_hour_near_or_above_ema200: bool = False
    one_hour_near_or_below_ema200: bool = False
    one_hour_close_above_ema200: bool = False
    one_hour_close_below_ema200: bool = False
    one_hour_ema50_slope_up: bool = False
    one_hour_ema50_slope_down: bool = False
    one_hour_higher_high: bool = False
    one_hour_higher_low: bool = False
    one_hour_lower_low: bool = False
    one_hour_lower_high: bool = False
    fifteen_close_above_ema200: bool = False
    fifteen_close_below_ema200: bool = False
    fifteen_ema50_slope_up: bool = False
    fifteen_ema50_slope_down: bool = False
    fifteen_breakout_high_volume: bool = False
    fifteen_breakdown_low_volume: bool = False
    fifteen_first_pullback_holds: bool = False
    fifteen_first_rebound_rejects: bool = False
    fifteen_ema50_above_ema200: bool = False
    fifteen_ema50_below_ema200: bool = False
    fifteen_reversal_candle: bool = False
    fifteen_rejection_candle: bool = False
    volume_confirmed: bool = False
    di_confirmed: bool = False
    atr_pct_extreme: bool = False
    ai_block: bool = False
    funding_block: bool = False
    account_risk_block: bool = False


@dataclass(frozen=True)
class ReversalSignal:
    action: str
    strategy_type: str
    signal_level: str | None
    score: Decimal
    risk_pct: Decimal | None
    max_standard_position_pct: Decimal | None
    reason: list[str]


def build_reversal_signal(
    trend: TrendResult,
    setup: ReversalSetup,
    min_entry_score: Decimal = Decimal("70"),
) -> ReversalSignal:
    if _blocked_by_risk_filter(setup):
        return _wait(Decimal("0"), ["risk filter blocked"])

    if trend.allow_reversal_long and trend.reversal_strategy_action == "EVALUATE_REVERSAL_LONG":
        return _build_long_signal(setup, min_entry_score)
    if trend.allow_reversal_short and trend.reversal_strategy_action == "EVALUATE_REVERSAL_SHORT":
        return _build_short_signal(setup, min_entry_score)
    return _wait(Decimal("0"), ["reversal trend not eligible"])


def _build_long_signal(setup: ReversalSetup, min_entry_score: Decimal) -> ReversalSignal:
    score = _score_long(setup)
    if _is_chasing_long(setup):
        return _wait(score, ["reversal long chasing blocked"])
    if score < min_entry_score:
        return _wait(score, ["reversal score below entry threshold"])
    if _confirmed_long(setup):
        return _entry("REVERSAL_LONG_ENTRY", "CONFIRMED", score, ["confirmed reversal long"])
    if _early_long(setup):
        return _entry("REVERSAL_LONG_ENTRY", "EARLY", score, ["early reversal long"])
    return _wait(score, ["reversal long conditions incomplete"])


def _build_short_signal(setup: ReversalSetup, min_entry_score: Decimal) -> ReversalSignal:
    score = _score_short(setup)
    if _is_chasing_short(setup):
        return _wait(score, ["reversal short chasing blocked"])
    if score < min_entry_score:
        return _wait(score, ["reversal score below entry threshold"])
    if _confirmed_short(setup):
        return _entry("REVERSAL_SHORT_ENTRY", "CONFIRMED", score, ["confirmed reversal short"])
    if _early_short(setup):
        return _entry("REVERSAL_SHORT_ENTRY", "EARLY", score, ["early reversal short"])
    return _wait(score, ["reversal short conditions incomplete"])


def _early_long(setup: ReversalSetup) -> bool:
    return all(
        [
            setup.four_hour_no_new_low,
            setup.one_hour_close_above_ema50,
            setup.one_hour_near_or_above_ema200,
            setup.fifteen_close_above_ema200,
            setup.fifteen_ema50_slope_up,
            setup.fifteen_breakout_high_volume,
            setup.fifteen_first_pullback_holds,
        ]
    )


def _confirmed_long(setup: ReversalSetup) -> bool:
    return all(
        [
            setup.four_hour_stop_structure,
            setup.one_hour_close_above_ema200,
            setup.one_hour_ema50_slope_up,
            setup.fifteen_ema50_above_ema200,
            setup.fifteen_first_pullback_holds,
            setup.fifteen_reversal_candle,
            setup.volume_confirmed,
        ]
    )


def _early_short(setup: ReversalSetup) -> bool:
    return all(
        [
            setup.four_hour_no_new_high,
            setup.one_hour_close_below_ema50,
            setup.one_hour_near_or_below_ema200,
            setup.fifteen_close_below_ema200,
            setup.fifteen_ema50_slope_down,
            setup.fifteen_breakdown_low_volume,
            setup.fifteen_first_rebound_rejects,
        ]
    )


def _confirmed_short(setup: ReversalSetup) -> bool:
    return all(
        [
            setup.four_hour_exhaustion_structure,
            setup.one_hour_close_below_ema200,
            setup.one_hour_ema50_slope_down,
            setup.fifteen_ema50_below_ema200,
            setup.fifteen_first_rebound_rejects,
            setup.fifteen_rejection_candle,
            setup.volume_confirmed,
        ]
    )


def _score_long(setup: ReversalSetup) -> Decimal:
    raw_score = Decimal("0")
    raw_score += Decimal("15") if setup.four_hour_stop_structure else Decimal("0")
    raw_score += Decimal("10") if setup.four_hour_near_or_above_ema50 else Decimal("0")
    raw_score += Decimal("10") if setup.one_hour_close_above_ema50 else Decimal("0")
    raw_score += Decimal("15") if setup.one_hour_close_above_ema200 else Decimal("0")
    raw_score += Decimal("10") if setup.one_hour_higher_high else Decimal("0")
    raw_score += Decimal("10") if setup.one_hour_higher_low else Decimal("0")
    raw_score += Decimal("10") if setup.fifteen_ema50_above_ema200 else Decimal("0")
    raw_score += Decimal("10") if setup.fifteen_first_pullback_holds else Decimal("0")
    raw_score += Decimal("5") if setup.fifteen_reversal_candle else Decimal("0")
    raw_score += Decimal("5") if setup.volume_confirmed else Decimal("0")
    raw_score += Decimal("5") if setup.di_confirmed else Decimal("0")
    return min(raw_score, Decimal("100"))


def _score_short(setup: ReversalSetup) -> Decimal:
    raw_score = Decimal("0")
    raw_score += Decimal("15") if setup.four_hour_exhaustion_structure else Decimal("0")
    raw_score += Decimal("10") if setup.four_hour_near_or_below_ema50 else Decimal("0")
    raw_score += Decimal("10") if setup.one_hour_close_below_ema50 else Decimal("0")
    raw_score += Decimal("15") if setup.one_hour_close_below_ema200 else Decimal("0")
    raw_score += Decimal("10") if setup.one_hour_lower_low else Decimal("0")
    raw_score += Decimal("10") if setup.one_hour_lower_high else Decimal("0")
    raw_score += Decimal("10") if setup.fifteen_ema50_below_ema200 else Decimal("0")
    raw_score += Decimal("10") if setup.fifteen_first_rebound_rejects else Decimal("0")
    raw_score += Decimal("5") if setup.fifteen_rejection_candle else Decimal("0")
    raw_score += Decimal("5") if setup.volume_confirmed else Decimal("0")
    raw_score += Decimal("5") if setup.di_confirmed else Decimal("0")
    return min(raw_score, Decimal("100"))


def _is_chasing_long(setup: ReversalSetup) -> bool:
    distance = setup.entry_price - setup.ema50_15m
    return distance > setup.atr_15m or _distance_pct(distance, setup.entry_price) > Decimal("0.012")


def _is_chasing_short(setup: ReversalSetup) -> bool:
    distance = setup.ema50_15m - setup.entry_price
    return distance > setup.atr_15m or _distance_pct(distance, setup.entry_price) > Decimal("0.012")


def _distance_pct(distance: Decimal, entry_price: Decimal) -> Decimal:
    if entry_price == 0:
        return Decimal("0")
    return distance / entry_price


def _blocked_by_risk_filter(setup: ReversalSetup) -> bool:
    return setup.atr_pct_extreme or setup.ai_block or setup.funding_block or setup.account_risk_block


def _entry(action: str, signal_level: str, score: Decimal, reason: list[str]) -> ReversalSignal:
    if signal_level == "EARLY":
        risk_pct = Decimal("0.002")
        max_position_pct = Decimal("0.2")
    else:
        risk_pct = Decimal("0.003")
        max_position_pct = Decimal("0.5")
    return ReversalSignal(
        action=action,
        strategy_type="REVERSAL_PROBE",
        signal_level=signal_level,
        score=score,
        risk_pct=risk_pct,
        max_standard_position_pct=max_position_pct,
        reason=reason,
    )


def _wait(score: Decimal, reason: list[str]) -> ReversalSignal:
    return ReversalSignal(
        action="WAIT",
        strategy_type="REVERSAL_PROBE",
        signal_level=None,
        score=score,
        risk_pct=None,
        max_standard_position_pct=None,
        reason=reason,
    )
