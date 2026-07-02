from dataclasses import dataclass
from decimal import Decimal

from app.data.quality import Kline
from app.indicators.core import atr, bollinger_bands, directional_movement_index, ema, ma
from app.paper.multitimeframe import MultiTimeframeFrame
from app.strategy.position_hierarchy import StrategyKernel, TradeMode, normalise_position_level, normalise_trade_mode
from app.strategy.signal_router import StrategySignal
from app.strategy.weekly_daily_h4_strategy import (
    OpenPositionState,
    TrendFrame,
    WeeklyDailyH4Config,
    WeeklyDailyH4Input,
    build_weekly_daily_h4_decision,
)


@dataclass(frozen=True)
class RealtimeStrategyConfig:
    fast_ma_type: str = "EMA"
    slow_ma_type: str = "MA"
    ema_fast_period: int = 15
    ema_slow_period: int = 60
    atr_period: int = 14
    dmi_period: int = 12
    swing_lookback: int = 20
    min_adx: Decimal = Decimal("18")
    min_risk_reward: Decimal = Decimal("1.5")
    target_risk_reward: Decimal = Decimal("2")
    daily_exit_policy: str = "FULL_REVERSAL"
    h4_rebound_adx_block_threshold: Decimal | None = Decimal("20")
    stop_atr_multiplier: Decimal = Decimal("1.5")
    max_same_direction_positions_per_level: int = 2
    weekly_max_same_direction_positions: int = 2
    daily_max_same_direction_positions: int = 1
    h4_max_same_direction_positions: int = 2
    strategy_kernel: str = StrategyKernel.WEEKLY_DAILY_H4_V1.value
    weekly_interval: str = "1w"
    daily_interval: str = "1d"
    h4_interval: str = "4h"
    main_trend_interval: str = "1w"
    trend_intervals: tuple[str, str] = ("1d", "4h")
    entry_interval: str = "4h"


def build_realtime_strategy_signal(
    frame: MultiTimeframeFrame,
    config: RealtimeStrategyConfig | None = None,
    open_buckets: tuple[str, ...] = (),
    open_strategy_types: tuple[str, ...] = (),
    current_interval: str | None = None,
) -> StrategySignal:
    strategy_config = config or RealtimeStrategyConfig()
    if strategy_config.strategy_kernel != StrategyKernel.WEEKLY_DAILY_H4_V1.value:
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=["unsupported strategy kernel; only WEEKLY_DAILY_H4_V1 is allowed"],
            strategy_kernel=StrategyKernel.WEEKLY_DAILY_H4_V1.value,
        )
    if not _has_required_history(frame, strategy_config):
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=["not enough closed klines for WEEKLY_DAILY_H4_V1 indicators"],
            strategy_kernel=StrategyKernel.WEEKLY_DAILY_H4_V1.value,
        )
    weekly = _build_trend_frame(frame.history(strategy_config.weekly_interval), strategy_config)
    daily = _build_trend_frame(frame.history(strategy_config.daily_interval), strategy_config)
    h4 = _build_trend_frame(frame.history(strategy_config.h4_interval), strategy_config, include_boll=True)
    if weekly is None or daily is None or h4 is None:
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=["WEEKLY_DAILY_H4_V1 indicators unavailable"],
            strategy_kernel=StrategyKernel.WEEKLY_DAILY_H4_V1.value,
        )
    decision = build_weekly_daily_h4_decision(
        WeeklyDailyH4Input(
            symbol=frame.symbol,
            weekly=weekly,
            daily=daily,
            h4=h4,
            open_positions=_open_position_states(open_buckets, open_strategy_types),
            focus_level=_focus_level_for_interval(current_interval, strategy_config),
        ),
        WeeklyDailyH4Config(
            min_adx=strategy_config.min_adx,
            target_risk_reward=strategy_config.target_risk_reward,
            daily_exit_policy=strategy_config.daily_exit_policy,
            h4_rebound_adx_block_threshold=strategy_config.h4_rebound_adx_block_threshold,
            stop_atr_multiplier=strategy_config.stop_atr_multiplier,
            max_same_direction_positions_per_level=strategy_config.max_same_direction_positions_per_level,
            weekly_max_same_direction_positions=strategy_config.weekly_max_same_direction_positions,
            daily_max_same_direction_positions=strategy_config.daily_max_same_direction_positions,
            h4_max_same_direction_positions=strategy_config.h4_max_same_direction_positions,
        ),
    )
    signal = decision.signal
    return StrategySignal(
        action=signal.action,
        strategy_type=signal.strategy_type,
        bucket=signal.bucket,
        reason=signal.reason,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        risk_reward=signal.risk_reward,
        signal_level=signal.signal_level,
        score=signal.score,
        risk_pct=signal.risk_pct,
        risk_multiplier=signal.risk_multiplier,
        trailing_atr=signal.trailing_atr,
        max_standard_position_pct=signal.max_standard_position_pct,
        core_rules=_core_rules(frame, strategy_config),
        chart_points=_chart_points(frame.history(strategy_config.h4_interval), strategy_config),
        chart_timeframes=_chart_timeframes(frame, strategy_config),
        condition_statuses=list(decision.diagnostics),
        nearest_strategy=_nearest_strategy(signal, list(decision.diagnostics)),
        strategy_kernel=signal.strategy_kernel,
        position_level=signal.position_level,
        trade_mode=signal.trade_mode,
        market_regime=signal.market_regime,
        lifecycle_state=signal.lifecycle_state,
        reduce_pct=signal.reduce_pct,
    )


def _has_required_history(frame: MultiTimeframeFrame, config: RealtimeStrategyConfig) -> bool:
    min_dmi_bars = config.dmi_period * 2 - 1
    min_bars = max(config.ema_slow_period, config.atr_period, config.swing_lookback, min_dmi_bars, 20, 2)
    return all(
        interval in frame.klines_by_interval and len(frame.history(interval)) >= min_bars
        for interval in (config.weekly_interval, config.daily_interval, config.h4_interval)
    )


def _focus_level_for_interval(interval: str | None, config: RealtimeStrategyConfig):
    if interval == config.weekly_interval:
        return normalise_position_level("WEEKLY")
    if interval == config.daily_interval:
        return normalise_position_level("DAILY")
    if interval == config.h4_interval:
        return normalise_position_level("H4")
    return None


def _build_trend_frame(
    klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
    include_boll: bool = False,
) -> TrendFrame | None:
    if len(klines) < 2:
        return None
    closes = [kline.close for kline in klines]
    highs = [kline.high for kline in klines]
    lows = [kline.low for kline in klines]
    fast_values = _moving_average(closes, config.ema_fast_period, config.fast_ma_type)
    slow_values = _moving_average(closes, config.ema_slow_period, config.slow_ma_type)
    atr_values = atr(highs, lows, closes, config.atr_period)
    movement_values = directional_movement_index(highs, lows, closes, config.dmi_period)
    fast = fast_values[-1]
    previous_fast = fast_values[-2]
    slow = slow_values[-1]
    latest_atr = atr_values[-1]
    movement = movement_values[-1]
    if fast is None or previous_fast is None or slow is None or latest_atr is None or movement is None:
        return None
    bands = bollinger_bands(closes, period=20, stddev=Decimal("2"))[-1] if include_boll else None
    structure_window = klines[-config.swing_lookback:-1]
    return TrendFrame(
        close=closes[-1],
        fast_ma=fast,
        slow_ma=slow,
        fast_ma_slope=fast - previous_fast,
        adx=movement.adx,
        di_plus=movement.di_plus,
        di_minus=movement.di_minus,
        previous_high=max((kline.high for kline in structure_window), default=None),
        previous_low=min((kline.low for kline in structure_window), default=None),
        boll_upper=bands.upper if bands is not None else None,
        boll_lower=bands.lower if bands is not None else None,
        boll_middle=bands.middle if bands is not None else None,
        atr=latest_atr,
    )


def _moving_average(values: list[Decimal], period: int, average_type: str) -> list[Decimal | None]:
    if _normalise_average_type(average_type) == "MA":
        return ma(values, period)
    return ema(values, period)


def _normalise_average_type(average_type: str) -> str:
    return average_type.upper() if average_type.upper() in {"EMA", "MA"} else "EMA"


def _average_label(average_type: str, period: int) -> str:
    return f"{_normalise_average_type(average_type)}{period}"


def _open_position_states(
    open_buckets: tuple[str, ...],
    open_strategy_types: tuple[str, ...],
) -> tuple[OpenPositionState, ...]:
    states: list[OpenPositionState] = []
    for encoded in open_strategy_types:
        parts = encoded.split("|")
        if len(parts) >= 4:
            level = normalise_position_level(parts[1])
            mode = normalise_trade_mode(parts[3])
            if level is not None and mode is not None:
                entry_count = _entry_count_from_encoded_parts(parts)
                lifecycle_parts = parts[4:-1] if parts and parts[-1].startswith("entries=") else parts[4:]
                lifecycle_state = "|".join(part for part in lifecycle_parts if part) if lifecycle_parts else "OPEN"
                lifecycle_state = lifecycle_state or "OPEN"
                states.append(
                    OpenPositionState(
                        symbol="",
                        side=parts[2],
                        position_level=level,
                        trade_mode=mode,
                        lifecycle_state=lifecycle_state,
                        entry_count=entry_count,
                    )
                )
    for bucket in open_buckets:
        level = normalise_position_level(bucket)
        if level is not None and all(state.position_level != level for state in states):
            states.append(OpenPositionState(symbol="", side="UNKNOWN", position_level=level, trade_mode=TradeMode.TREND))
    return tuple(states)


def _entry_count_from_encoded_parts(parts: list[str]) -> int:
    if not parts or not parts[-1].startswith("entries="):
        return 1
    try:
        return max(1, int(parts[-1].split("=", 1)[1]))
    except ValueError:
        return 1


def _core_rules(frame: MultiTimeframeFrame, config: RealtimeStrategyConfig) -> list[str]:
    rules: list[str] = [f"strategy_kernel={StrategyKernel.WEEKLY_DAILY_H4_V1.value}"]
    for interval in (config.weekly_interval, config.daily_interval, config.h4_interval):
        klines = frame.history(interval)
        trend = _build_trend_frame(klines, config, include_boll=interval == config.h4_interval)
        if trend is None:
            continue
        rules.append(
            f"{interval}: close={trend.close} {_average_label(config.fast_ma_type, config.ema_fast_period)}={trend.fast_ma} "
            f"{_average_label(config.slow_ma_type, config.ema_slow_period)}={trend.slow_ma} ADX={trend.adx}"
        )
    return rules


def _chart_points(klines: tuple[Kline, ...], config: RealtimeStrategyConfig) -> list[dict[str, str]]:
    closes = [kline.close for kline in klines]
    fast_values = _moving_average(closes, config.ema_fast_period, config.fast_ma_type)
    slow_values = _moving_average(closes, config.ema_slow_period, config.slow_ma_type)
    points: list[dict[str, str]] = []
    for kline, fast, slow in zip(klines[-80:], fast_values[-80:], slow_values[-80:]):
        points.append(
            {
                "open_time": str(kline.open_time),
                "close_time": str(kline.close_time),
                "open": str(kline.open),
                "high": str(kline.high),
                "low": str(kline.low),
                "close": str(kline.close),
                "fast_ma": str(fast) if fast is not None else "",
                "slow_ma": str(slow) if slow is not None else "",
            }
        )
    return points


def _chart_timeframes(frame: MultiTimeframeFrame, config: RealtimeStrategyConfig) -> dict[str, list[dict[str, str]]]:
    return {
        interval: _chart_points(frame.history(interval), config)
        for interval in (config.weekly_interval, config.daily_interval, config.h4_interval)
        if interval in frame.klines_by_interval
    }


def _nearest_strategy(signal: StrategySignal, diagnostics: list[dict[str, object]]) -> dict[str, object]:
    required = [item for item in diagnostics if item.get("required", True)]
    return {
        "name": signal.strategy_type if signal.strategy_type != "SYSTEM" else StrategyKernel.WEEKLY_DAILY_H4_V1.value,
        "matched": sum(1 for item in required if item.get("passed")),
        "total": len(required),
        "action": signal.action,
    }
