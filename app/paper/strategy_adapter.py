from dataclasses import dataclass
from decimal import Decimal

from app.data.quality import Kline
from app.indicators.core import atr, directional_movement_index, ema
from app.paper.multitimeframe import MultiTimeframeFrame
from app.strategy.pullback_strategy import EntryFrame, TradeSignal, build_pullback_signal
from app.strategy.signal_router import StrategySignal
from app.strategy.trend_detector import TrendFrame, detect_trend


@dataclass(frozen=True)
class RealtimeStrategyConfig:
    ema_fast_period: int = 50
    ema_slow_period: int = 200
    atr_period: int = 14
    dmi_period: int = 14
    swing_lookback: int = 20
    min_adx: Decimal = Decimal("20")
    min_risk_reward: Decimal = Decimal("1.5")
    target_risk_reward: Decimal = Decimal("2")
    trend_intervals: tuple[str, str] = ("4h", "1h")
    entry_interval: str = "15m"


def build_realtime_strategy_signal(
    frame: MultiTimeframeFrame,
    config: RealtimeStrategyConfig | None = None,
) -> TradeSignal | StrategySignal:
    strategy_config = config or RealtimeStrategyConfig()
    if not _has_required_history(frame, strategy_config):
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=["not enough closed klines for realtime indicators"],
        )

    four_hour_interval, one_hour_interval = strategy_config.trend_intervals
    four_hour = _build_trend_frame(frame.history(four_hour_interval), strategy_config)
    one_hour = _build_trend_frame(frame.history(one_hour_interval), strategy_config)
    entry_frame = _build_entry_frame(frame.history(strategy_config.entry_interval), strategy_config)
    if four_hour is None or one_hour is None or entry_frame is None:
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=["realtime indicators unavailable"],
        )

    trend = detect_trend(
        four_hour=four_hour,
        one_hour=one_hour,
        min_adx=strategy_config.min_adx,
    )
    return build_pullback_signal(
        trend=trend,
        frame=entry_frame,
        min_risk_reward=strategy_config.min_risk_reward,
        target_risk_reward=strategy_config.target_risk_reward,
    )


def _has_required_history(frame: MultiTimeframeFrame, config: RealtimeStrategyConfig) -> bool:
    min_trend_bars = max(config.ema_slow_period, config.dmi_period, 2)
    min_entry_bars = max(config.ema_fast_period, config.atr_period, config.swing_lookback, 2)
    for interval in config.trend_intervals:
        if len(frame.history(interval)) < min_trend_bars:
            return False
    return len(frame.history(config.entry_interval)) >= min_entry_bars


def _build_trend_frame(
    klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
) -> TrendFrame | None:
    closes = [kline.close for kline in klines]
    highs = [kline.high for kline in klines]
    lows = [kline.low for kline in klines]
    fast_ema = ema(closes, config.ema_fast_period)
    slow_ema = ema(closes, config.ema_slow_period)
    movement = directional_movement_index(highs, lows, closes, config.dmi_period)
    latest_fast = fast_ema[-1]
    previous_fast = fast_ema[-2]
    latest_slow = slow_ema[-1]
    latest_movement = movement[-1]
    if (
        latest_fast is None
        or previous_fast is None
        or latest_slow is None
        or latest_movement is None
    ):
        return None
    return TrendFrame(
        close=closes[-1],
        ema50=latest_fast,
        ema200=latest_slow,
        ema50_slope=latest_fast - previous_fast,
        di_plus=latest_movement.di_plus,
        di_minus=latest_movement.di_minus,
        adx=latest_movement.adx,
    )


def _build_entry_frame(
    klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
) -> EntryFrame | None:
    closes = [kline.close for kline in klines]
    highs = [kline.high for kline in klines]
    lows = [kline.low for kline in klines]
    fast_ema = ema(closes, config.ema_fast_period)
    atr_values = atr(highs, lows, closes, config.atr_period)
    latest_ema = fast_ema[-1]
    latest_atr = atr_values[-1]
    if latest_ema is None or latest_atr is None:
        return None
    swing_window = klines[-config.swing_lookback :]
    return EntryFrame(
        close=closes[-1],
        previous_close=closes[-2],
        ema50=latest_ema,
        atr=latest_atr,
        recent_swing_low=min(kline.low for kline in swing_window),
        recent_swing_high=max(kline.high for kline in swing_window),
    )
