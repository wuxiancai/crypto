from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TrendFrame:
    close: Decimal
    ema50: Decimal
    ema200: Decimal
    ema50_slope: Decimal
    di_plus: Decimal
    di_minus: Decimal
    adx: Decimal


@dataclass(frozen=True)
class TrendResult:
    trend_state: str
    main_strategy_action: str
    reversal_strategy_action: str
    allow_long: bool
    allow_short: bool
    allow_reversal_long: bool
    allow_reversal_short: bool
    reason: list[str]


def detect_trend(four_hour: TrendFrame, one_hour: TrendFrame, min_adx: Decimal = Decimal("20")) -> TrendResult:
    four_up = _is_uptrend(four_hour, min_adx)
    four_down = _is_downtrend(four_hour, min_adx)
    one_up = _is_uptrend(one_hour, min_adx)
    one_down = _is_downtrend(one_hour, min_adx)

    if four_up and one_up:
        return TrendResult(
            trend_state="UPTREND",
            main_strategy_action="EVALUATE_LONG",
            reversal_strategy_action="DISABLED",
            allow_long=True,
            allow_short=False,
            allow_reversal_long=False,
            allow_reversal_short=False,
            reason=["4h uptrend", "1h uptrend"],
        )
    if four_down and one_down:
        return TrendResult(
            trend_state="DOWNTREND",
            main_strategy_action="EVALUATE_SHORT",
            reversal_strategy_action="DISABLED",
            allow_long=False,
            allow_short=True,
            allow_reversal_long=False,
            allow_reversal_short=False,
            reason=["4h downtrend", "1h downtrend"],
        )
    if four_down and one_up:
        return TrendResult(
            trend_state="TRANSITION",
            main_strategy_action="WAIT",
            reversal_strategy_action="EVALUATE_REVERSAL_LONG",
            allow_long=False,
            allow_short=False,
            allow_reversal_long=True,
            allow_reversal_short=False,
            reason=["4h downtrend", "1h uptrend"],
        )
    if four_up and one_down:
        return TrendResult(
            trend_state="TRANSITION",
            main_strategy_action="WAIT",
            reversal_strategy_action="EVALUATE_REVERSAL_SHORT",
            allow_long=False,
            allow_short=False,
            allow_reversal_long=False,
            allow_reversal_short=True,
            reason=["4h uptrend", "1h downtrend"],
        )
    return TrendResult(
        trend_state="RANGE",
        main_strategy_action="WAIT",
        reversal_strategy_action="WAIT",
        allow_long=False,
        allow_short=False,
        allow_reversal_long=False,
        allow_reversal_short=False,
        reason=["trend unclear"],
    )


def _is_uptrend(frame: TrendFrame, min_adx: Decimal) -> bool:
    return (
        frame.close > frame.ema200
        and frame.ema50 > frame.ema200
        and frame.ema50_slope > 0
        and frame.adx >= min_adx
        and frame.di_plus > frame.di_minus
    )


def _is_downtrend(frame: TrendFrame, min_adx: Decimal) -> bool:
    return (
        frame.close < frame.ema200
        and frame.ema50 < frame.ema200
        and frame.ema50_slope < 0
        and frame.adx >= min_adx
        and frame.di_minus > frame.di_plus
    )

