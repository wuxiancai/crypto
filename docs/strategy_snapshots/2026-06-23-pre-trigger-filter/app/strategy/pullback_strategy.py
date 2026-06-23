from dataclasses import dataclass
from decimal import Decimal

from app.strategy.trend_detector import TrendResult


@dataclass(frozen=True)
class EntryFrame:
    close: Decimal
    previous_close: Decimal
    ema50: Decimal
    atr: Decimal
    recent_swing_low: Decimal
    recent_swing_high: Decimal
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None


@dataclass(frozen=True)
class TradeSignal:
    action: str
    strategy_type: str
    entry_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    risk_reward: Decimal | None
    reason: list[str]


def build_pullback_signal(
    trend: TrendResult,
    frame: EntryFrame,
    min_risk_reward: Decimal = Decimal("1.5"),
    target_risk_reward: Decimal = Decimal("2"),
) -> TradeSignal:
    if trend.allow_long and trend.main_strategy_action == "EVALUATE_LONG":
        return _build_long_signal(frame, min_risk_reward, target_risk_reward)
    if trend.allow_short and trend.main_strategy_action == "EVALUATE_SHORT":
        return _build_short_signal(frame, min_risk_reward, target_risk_reward)
    return _wait(["main trend not eligible"])


def _build_long_signal(frame: EntryFrame, min_risk_reward: Decimal, target_risk_reward: Decimal) -> TradeSignal:
    reason = ["main trend uptrend"]
    if not _pullback_to_ema50_zone(frame):
        return _wait(reason + ["price not in ema50 pullback zone"])
    reason.append("price pulled back to ema50 zone")
    if not _bullish_confirmation(frame):
        return _wait(reason + ["missing bullish 15m confirmation"])
    reason.append("bullish 15m confirmation")

    entry_price = frame.close
    stop_loss = frame.recent_swing_low
    risk_per_unit = entry_price - stop_loss
    if risk_per_unit <= 0:
        return _wait(reason + ["invalid stop loss"])
    take_profit = entry_price + risk_per_unit * target_risk_reward
    risk_reward = (take_profit - entry_price) / risk_per_unit
    if risk_reward < min_risk_reward:
        return _wait(reason + ["risk reward too low"])

    return TradeSignal(
        action="LONG_ENTRY",
        strategy_type="TREND_PULLBACK",
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=risk_reward,
        reason=reason + ["risk reward accepted"],
    )


def _build_short_signal(frame: EntryFrame, min_risk_reward: Decimal, target_risk_reward: Decimal) -> TradeSignal:
    reason = ["main trend downtrend"]
    if not _rebound_to_ema50_zone(frame):
        return _wait(reason + ["price not in ema50 rebound zone"])
    reason.append("price rebounded to ema50 zone")
    if not _bearish_confirmation(frame):
        return _wait(reason + ["missing bearish 15m confirmation"])
    reason.append("bearish 15m confirmation")

    entry_price = frame.close
    stop_loss = frame.recent_swing_high
    risk_per_unit = stop_loss - entry_price
    if risk_per_unit <= 0:
        return _wait(reason + ["invalid stop loss"])
    take_profit = entry_price - risk_per_unit * target_risk_reward
    risk_reward = (entry_price - take_profit) / risk_per_unit
    if risk_reward < min_risk_reward:
        return _wait(reason + ["risk reward too low"])

    return TradeSignal(
        action="SHORT_ENTRY",
        strategy_type="TREND_PULLBACK",
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=risk_reward,
        reason=reason + ["risk reward accepted"],
    )


def _pullback_to_ema50_zone(frame: EntryFrame) -> bool:
    low = frame.low if frame.low is not None else frame.close
    return low <= frame.ema50 + frame.atr and frame.close >= frame.ema50 - frame.atr


def _rebound_to_ema50_zone(frame: EntryFrame) -> bool:
    high = frame.high if frame.high is not None else frame.close
    return high >= frame.ema50 - frame.atr and frame.close <= frame.ema50 + frame.atr


def _bullish_confirmation(frame: EntryFrame) -> bool:
    if frame.open is not None:
        return frame.close > frame.open
    return frame.close > frame.previous_close


def _bearish_confirmation(frame: EntryFrame) -> bool:
    if frame.open is not None:
        return frame.close < frame.open
    return frame.close < frame.previous_close


def _near_ema50(frame: EntryFrame) -> bool:
    return abs(frame.close - frame.ema50) <= frame.atr


def _wait(reason: list[str]) -> TradeSignal:
    return TradeSignal(
        action="WAIT",
        strategy_type="TREND_PULLBACK",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        risk_reward=None,
        reason=reason,
    )
