from dataclasses import dataclass
from decimal import Decimal

from app.data.quality import Kline
from app.indicators.core import atr, directional_movement_index, ema, ma
from app.paper.multitimeframe import MultiTimeframeFrame
from app.strategy.pullback_strategy import EntryFrame, PullbackTriggerConfig, TradeSignal, build_pullback_signal
from app.strategy.reversal_strategy import ReversalSetup, build_reversal_signal
from app.strategy.signal_router import SignalInputs, StrategySignal, select_signal
from app.strategy.trend_detector import TrendFrame, detect_trend
from app.strategy.layered_strategy import (
    LayeredEntryFrame,
    LayeredStrategyConfig,
    LayeredStrategyInput,
    TrendRegime,
    TrendSnapshot,
    build_layered_strategy_decision,
)


@dataclass(frozen=True)
class RealtimeStrategyConfig:
    fast_ma_type: str = "EMA"
    slow_ma_type: str = "EMA"
    ema_fast_period: int = 50
    ema_slow_period: int = 200
    atr_period: int = 14
    dmi_period: int = 14
    swing_lookback: int = 20
    min_adx: Decimal = Decimal("20")
    min_risk_reward: Decimal = Decimal("1.5")
    target_risk_reward: Decimal = Decimal("2")
    pullback_zone_atr_multiplier: Decimal = Decimal("1")
    require_pullback_close_beyond_fast_ma: bool = False
    enable_reversal_probe: bool = True
    enable_layered_strategy: bool = False
    main_trend_interval: str = "1d"
    trend_intervals: tuple[str, str] = ("4h", "1h")
    entry_interval: str = "15m"


def build_realtime_strategy_signal(
    frame: MultiTimeframeFrame,
    config: RealtimeStrategyConfig | None = None,
    open_buckets: tuple[str, ...] = (),
    open_strategy_types: tuple[str, ...] = (),
) -> TradeSignal | StrategySignal:
    strategy_config = config or RealtimeStrategyConfig()
    if not _has_required_history(frame, strategy_config):
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=["not enough closed klines for realtime indicators"],
        )
    layered_signal = (
        _build_layered_signal_if_available(
            frame=frame,
            config=strategy_config,
            open_buckets=open_buckets,
            open_strategy_types=open_strategy_types,
        )
        if strategy_config.enable_layered_strategy
        else None
    )
    if layered_signal is not None:
        return _attach_realtime_diagnostics(signal=layered_signal, frame=frame, config=strategy_config)

    four_hour_interval, one_hour_interval = strategy_config.trend_intervals
    four_hour = _build_trend_frame(frame.history(four_hour_interval), strategy_config)
    one_hour = _build_trend_frame(frame.history(one_hour_interval), strategy_config)
    entry_frame = _build_entry_frame(frame.history(strategy_config.entry_interval), strategy_config)
    reversal_setup = _build_reversal_setup(
        four_hour_klines=frame.history(four_hour_interval),
        one_hour_klines=frame.history(one_hour_interval),
        entry_klines=frame.history(strategy_config.entry_interval),
        config=strategy_config,
    )
    if four_hour is None or one_hour is None or entry_frame is None or reversal_setup is None:
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
    main_signal = build_pullback_signal(
        trend=trend,
        frame=entry_frame,
        min_risk_reward=strategy_config.min_risk_reward,
        target_risk_reward=strategy_config.target_risk_reward,
        trigger_config=PullbackTriggerConfig(
            zone_atr_multiplier=strategy_config.pullback_zone_atr_multiplier,
            require_close_beyond_ema=strategy_config.require_pullback_close_beyond_fast_ma,
        ),
    )
    reversal_signal = (
        build_reversal_signal(trend=trend, setup=reversal_setup)
        if strategy_config.enable_reversal_probe
        else TradeSignal(
            action="WAIT",
            strategy_type="REVERSAL_PROBE",
            entry_price=None,
            stop_loss=None,
            take_profit=None,
            risk_reward=None,
            reason=["reversal probe disabled"],
        )
    )
    signal = select_signal(SignalInputs(main_signal=main_signal, reversal_signal=reversal_signal))
    return _attach_realtime_diagnostics(signal=signal, frame=frame, config=strategy_config)


def _has_required_history(frame: MultiTimeframeFrame, config: RealtimeStrategyConfig) -> bool:
    min_dmi_bars = config.dmi_period * 2 - 1
    min_trend_bars = max(config.ema_slow_period, min_dmi_bars, 2)
    min_entry_bars = max(config.ema_fast_period, config.atr_period, config.swing_lookback, min_dmi_bars, 2)
    for interval in config.trend_intervals:
        if len(frame.history(interval)) < min_trend_bars:
            return False
    if (
        config.enable_layered_strategy
        and _has_interval(frame, config.main_trend_interval)
        and len(frame.history(config.main_trend_interval)) < min_trend_bars
    ):
        return False
    return len(frame.history(config.entry_interval)) >= min_entry_bars


def _has_interval(frame: MultiTimeframeFrame, interval: str) -> bool:
    return interval in frame.klines_by_interval


def _build_layered_signal_if_available(
    frame: MultiTimeframeFrame,
    config: RealtimeStrategyConfig,
    open_buckets: tuple[str, ...] = (),
    open_strategy_types: tuple[str, ...] = (),
) -> StrategySignal | None:
    if not _has_interval(frame, config.main_trend_interval):
        return None
    four_hour_interval, one_hour_interval = config.trend_intervals
    daily = _build_trend_frame(frame.history(config.main_trend_interval), config)
    four_hour = _build_trend_frame(frame.history(four_hour_interval), config)
    one_hour = _build_trend_frame(frame.history(one_hour_interval), config)
    daily_regime = _trend_regime_from_history(frame.history(config.main_trend_interval), config)
    four_hour_regime = _trend_regime_from_history(frame.history(four_hour_interval), config)
    one_hour_regime = _trend_regime_from_history(frame.history(one_hour_interval), config)
    entry_frame = _build_entry_frame(frame.history(config.entry_interval), config)
    if daily is None or four_hour is None or one_hour is None or entry_frame is None:
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=["layered strategy indicators unavailable"],
        )
    decision = build_layered_strategy_decision(
        LayeredStrategyInput(
            symbol=frame.symbol,
            daily=_trend_snapshot_from(daily),
            four_hour=_trend_snapshot_from(four_hour),
            one_hour=_trend_snapshot_from(one_hour),
            entry=LayeredEntryFrame(
                close=entry_frame.close,
                open=entry_frame.open or entry_frame.close,
                high=entry_frame.high or entry_frame.close,
                low=entry_frame.low or entry_frame.close,
                fast_ma=entry_frame.ema50,
                atr=entry_frame.atr,
                recent_swing_low=entry_frame.recent_swing_low,
                recent_swing_high=entry_frame.recent_swing_high,
            ),
            daily_regime=daily_regime,
            four_hour_regime=four_hour_regime,
            one_hour_regime=one_hour_regime,
            open_buckets=open_buckets,
            open_strategy_types=open_strategy_types,
        ),
        LayeredStrategyConfig(
            min_adx=config.min_adx,
            target_risk_reward=config.target_risk_reward,
        ),
    )
    if decision.signal is None:
        diagnostics = list(decision.diagnostics)
        return StrategySignal(
            action="WAIT",
            strategy_type="SYSTEM",
            reason=["no layered strategy candidate ready"],
            condition_statuses=diagnostics,
            nearest_strategy=_nearest_layered_strategy(decision.candidates, diagnostics),
        )
    diagnostics = list(decision.diagnostics)
    nearest_strategy = _nearest_layered_strategy((decision.signal.strategy_type,), diagnostics)
    nearest_strategy["action"] = decision.signal.action
    return StrategySignal(
        action=decision.signal.action,
        strategy_type=decision.signal.strategy_type,
        bucket=decision.signal.bucket,
        reason=[*decision.signal.reason, f"candidates={','.join(decision.candidates)}"],
        entry_price=decision.signal.entry_price,
        stop_loss=decision.signal.stop_loss,
        take_profit=decision.signal.take_profit,
        risk_reward=decision.signal.risk_reward,
        risk_pct=decision.signal.risk_pct,
        trailing_atr=decision.signal.trailing_atr,
        condition_statuses=diagnostics,
        nearest_strategy=nearest_strategy,
    )


def _nearest_layered_strategy(
    candidates: tuple[str, ...],
    diagnostics: list[dict[str, object]],
) -> dict[str, object]:
    if candidates:
        name = candidates[0]
    elif diagnostics:
        name = str(diagnostics[0].get("strategy") or diagnostics[0].get("strategy_type") or "SYSTEM")
    else:
        name = "SYSTEM"
    selected = [
        diagnostic
        for diagnostic in diagnostics
        if str(diagnostic.get("strategy") or diagnostic.get("strategy_type") or "") == name
    ]
    if not selected and not candidates:
        selected = diagnostics
    required = [diagnostic for diagnostic in selected if diagnostic.get("required", True)]
    return {
        "name": name,
        "matched": sum(1 for diagnostic in required if diagnostic.get("passed")),
        "total": len(required),
        "action": "WAIT",
    }


def _trend_snapshot_from(frame: TrendFrame) -> TrendSnapshot:
    return TrendSnapshot(
        close=frame.close,
        fast_ma=frame.ema50,
        slow_ma=frame.ema200,
        fast_ma_slope=frame.ema50_slope,
        adx=frame.adx,
        di_plus=frame.di_plus,
        di_minus=frame.di_minus,
    )


def _trend_regime_from_history(
    klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
) -> TrendRegime:
    return _trend_regime_from_snapshots(_trend_snapshots_from_history(klines, config), config)


def _trend_snapshots_from_history(
    klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
) -> list[tuple[int, TrendSnapshot]]:
    if len(klines) < 2:
        return []
    closes = [kline.close for kline in klines]
    highs = [kline.high for kline in klines]
    lows = [kline.low for kline in klines]
    fast_values = _moving_average(closes, config.ema_fast_period, config.fast_ma_type)
    slow_values = _moving_average(closes, config.ema_slow_period, config.slow_ma_type)
    movement_values = directional_movement_index(highs, lows, closes, config.dmi_period)
    snapshots: list[tuple[int, TrendSnapshot]] = []
    for index in range(1, len(klines)):
        fast = fast_values[index]
        previous_fast = fast_values[index - 1]
        slow = slow_values[index]
        movement = movement_values[index]
        if fast is None or previous_fast is None or slow is None or movement is None:
            continue
        snapshots.append(
            (
                klines[index].close_time,
                TrendSnapshot(
                    close=closes[index],
                    fast_ma=fast,
                    slow_ma=slow,
                    fast_ma_slope=fast - previous_fast,
                    adx=movement.adx,
                    di_plus=movement.di_plus,
                    di_minus=movement.di_minus,
                ),
            )
        )
    return snapshots


def _trend_regime_from_snapshots(
    snapshots: list[tuple[int, TrendSnapshot]],
    config: RealtimeStrategyConfig,
) -> TrendRegime:
    direction = "UNKNOWN"
    confirmed_at_ms: int | None = None
    layered_config = LayeredStrategyConfig(min_adx=config.min_adx)
    for confirmed_at, snapshot in snapshots:
        if _snapshot_bearish_confirmed(snapshot, layered_config):
            direction = "SHORT"
            confirmed_at_ms = confirmed_at
        elif _snapshot_bullish_confirmed(snapshot, layered_config):
            direction = "LONG"
            confirmed_at_ms = confirmed_at
    return TrendRegime(direction=direction, confirmed_at_ms=confirmed_at_ms)


def _snapshot_bullish_confirmed(snapshot: TrendSnapshot, config: LayeredStrategyConfig) -> bool:
    return (
        snapshot.fast_ma > snapshot.slow_ma
        and snapshot.fast_ma_slope > 0
        and snapshot.adx >= config.min_adx
        and snapshot.di_plus > snapshot.di_minus
    )


def _snapshot_bearish_confirmed(snapshot: TrendSnapshot, config: LayeredStrategyConfig) -> bool:
    return (
        snapshot.fast_ma < snapshot.slow_ma
        and snapshot.fast_ma_slope < 0
        and snapshot.adx >= config.min_adx
        and snapshot.di_minus > snapshot.di_plus
    )


def _moving_average(values: list[Decimal], period: int, average_type: str) -> list[Decimal | None]:
    if _normalise_average_type(average_type) == "MA":
        return ma(values, period)
    return ema(values, period)


def _average_label(average_type: str, period: int) -> str:
    return f"{_normalise_average_type(average_type)}{period}"


def _normalise_average_type(average_type: str) -> str:
    return average_type.upper() if average_type.upper() in {"EMA", "MA"} else "EMA"


def _build_trend_frame(
    klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
) -> TrendFrame | None:
    closes = [kline.close for kline in klines]
    highs = [kline.high for kline in klines]
    lows = [kline.low for kline in klines]
    fast_ema = _moving_average(closes, config.ema_fast_period, config.fast_ma_type)
    slow_ema = _moving_average(closes, config.ema_slow_period, config.slow_ma_type)
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
    fast_ema = _moving_average(closes, config.ema_fast_period, config.fast_ma_type)
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
        open=klines[-1].open,
        high=klines[-1].high,
        low=klines[-1].low,
    )


def _build_reversal_setup(
    four_hour_klines: tuple[Kline, ...],
    one_hour_klines: tuple[Kline, ...],
    entry_klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
) -> ReversalSetup | None:
    four_hour_entry = _build_entry_frame(four_hour_klines, config)
    one_hour_trend = _build_trend_frame(one_hour_klines, config)
    entry_trend = _build_trend_frame(entry_klines, config)
    entry_frame = _build_entry_frame(entry_klines, config)
    if (
        four_hour_entry is None
        or one_hour_trend is None
        or entry_trend is None
        or entry_frame is None
    ):
        return None

    four_latest = four_hour_klines[-1]
    four_previous = four_hour_klines[-2]
    one_latest = one_hour_klines[-1]
    one_previous = one_hour_klines[-2]
    entry_latest = entry_klines[-1]
    entry_previous = entry_klines[-2]
    average_volume = sum(kline.volume for kline in entry_klines[-config.swing_lookback :]) / Decimal(
        len(entry_klines[-config.swing_lookback :])
    )

    return ReversalSetup(
        entry_price=entry_latest.close,
        ema50_15m=entry_trend.ema50,
        atr_15m=entry_frame.atr,
        four_hour_no_new_low=four_latest.low >= min(kline.low for kline in four_hour_klines[:-1]),
        four_hour_no_new_high=four_latest.high <= max(kline.high for kline in four_hour_klines[:-1]),
        four_hour_stop_structure=four_latest.close > four_previous.close,
        four_hour_exhaustion_structure=four_latest.close < four_previous.close,
        four_hour_near_or_above_ema50=four_latest.close >= four_hour_entry.ema50 - four_hour_entry.atr,
        four_hour_near_or_below_ema50=four_latest.close <= four_hour_entry.ema50 + four_hour_entry.atr,
        one_hour_close_above_ema50=one_hour_trend.close > one_hour_trend.ema50,
        one_hour_close_below_ema50=one_hour_trend.close < one_hour_trend.ema50,
        one_hour_near_or_above_ema200=one_hour_trend.close >= one_hour_trend.ema200 - entry_frame.atr,
        one_hour_near_or_below_ema200=one_hour_trend.close <= one_hour_trend.ema200 + entry_frame.atr,
        one_hour_close_above_ema200=one_hour_trend.close > one_hour_trend.ema200,
        one_hour_close_below_ema200=one_hour_trend.close < one_hour_trend.ema200,
        one_hour_ema50_slope_up=one_hour_trend.ema50_slope > 0,
        one_hour_ema50_slope_down=one_hour_trend.ema50_slope < 0,
        one_hour_higher_high=one_latest.high > one_previous.high,
        one_hour_higher_low=one_latest.low > one_previous.low,
        one_hour_lower_low=one_latest.low < one_previous.low,
        one_hour_lower_high=one_latest.high < one_previous.high,
        fifteen_close_above_ema200=entry_trend.close > entry_trend.ema200,
        fifteen_close_below_ema200=entry_trend.close < entry_trend.ema200,
        fifteen_ema50_slope_up=entry_trend.ema50_slope > 0,
        fifteen_ema50_slope_down=entry_trend.ema50_slope < 0,
        fifteen_breakout_high_volume=entry_latest.close >= entry_previous.close
        and entry_latest.volume >= average_volume,
        fifteen_breakdown_low_volume=entry_latest.close <= entry_previous.close
        and entry_latest.volume >= average_volume,
        fifteen_first_pullback_holds=entry_latest.low >= entry_frame.ema50 - entry_frame.atr,
        fifteen_first_rebound_rejects=entry_latest.high <= entry_frame.ema50 + entry_frame.atr,
        fifteen_ema50_above_ema200=entry_trend.ema50 > entry_trend.ema200,
        fifteen_ema50_below_ema200=entry_trend.ema50 < entry_trend.ema200,
        fifteen_reversal_candle=entry_latest.close > entry_latest.open,
        fifteen_rejection_candle=entry_latest.close < entry_latest.open,
        volume_confirmed=entry_latest.volume >= average_volume,
        di_confirmed=(
            entry_trend.di_plus > entry_trend.di_minus
            if entry_trend.ema50_slope > 0
            else entry_trend.di_minus > entry_trend.di_plus
        ),
    )


def _attach_realtime_diagnostics(
    signal: StrategySignal,
    frame: MultiTimeframeFrame,
    config: RealtimeStrategyConfig,
) -> StrategySignal:
    condition_statuses = signal.condition_statuses or _condition_statuses(frame=frame, config=config)
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
        core_rules=_core_rules(frame=frame, config=config),
        chart_points=_chart_points(frame.history(config.entry_interval), config=config),
        chart_timeframes=_chart_timeframes(frame=frame, config=config),
        condition_statuses=condition_statuses,
        nearest_strategy=signal.nearest_strategy or _nearest_strategy(condition_statuses),
    )


def _core_rules(frame: MultiTimeframeFrame, config: RealtimeStrategyConfig) -> list[str]:
    rules: list[str] = []
    intervals = (
        (config.main_trend_interval,) if _has_interval(frame, config.main_trend_interval) else ()
    ) + (*config.trend_intervals, config.entry_interval)
    for interval in intervals:
        klines = frame.history(interval)
        closes = [kline.close for kline in klines]
        if not closes:
            continue
        fast = _moving_average(closes, config.ema_fast_period, config.fast_ma_type)[-1]
        slow = _moving_average(closes, config.ema_slow_period, config.slow_ma_type)[-1]
        if fast is None or slow is None:
            continue
        fast_label = _average_label(config.fast_ma_type, config.ema_fast_period)
        slow_label = _average_label(config.slow_ma_type, config.ema_slow_period)
        if fast > slow:
            rules.append(f"{interval} {fast_label} > {slow_label}：多头基础")
        elif slow > fast:
            rules.append(f"{interval} {slow_label} > {fast_label}：空头基础")
        else:
            rules.append(f"{interval} {fast_label} = {slow_label}：方向不明")
    rules.append(
        f"分层策略：1d 主趋势 + 4h 子趋势 + 1h 确认 + 15m {_average_label(config.fast_ma_type, config.ema_fast_period)} 入场"
    )
    rules.append("策略候选：DAY_CORE / FOUR_HOUR_ADDON / FOUR_HOUR_HEDGE")
    return rules


def _chart_points(
    klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
    max_points: int = 80,
) -> list[dict[str, str]]:
    if not klines:
        return []
    closes = [kline.close for kline in klines]
    fast_values = _moving_average(closes, config.ema_fast_period, config.fast_ma_type)
    slow_values = _moving_average(closes, config.ema_slow_period, config.slow_ma_type)
    fast_label = _average_label(config.fast_ma_type, config.ema_fast_period)
    slow_label = _average_label(config.slow_ma_type, config.ema_slow_period)
    start = max(0, len(klines) - max_points)
    points: list[dict[str, str]] = []
    for kline, fast_value, slow_value in zip(
        klines[start:],
        fast_values[start:],
        slow_values[start:],
        strict=True,
    ):
        point = {
            "open_time": str(kline.open_time),
            "open": str(kline.open),
            "high": str(kline.high),
            "low": str(kline.low),
            "close": str(kline.close),
            "fast_ma_label": fast_label,
            "slow_ma_label": slow_label,
        }
        if fast_value is not None:
            point["ma_fast"] = str(fast_value)
            point["ema50"] = str(fast_value)
        if slow_value is not None:
            point["ma_slow"] = str(slow_value)
            point["ema200"] = str(slow_value)
        points.append(point)
    return points


def _chart_timeframes(
    frame: MultiTimeframeFrame,
    config: RealtimeStrategyConfig,
) -> dict[str, list[dict[str, str]]]:
    return {
        interval: _chart_points(frame.history(interval), config=config)
        for interval in (
            ((config.main_trend_interval,) if _has_interval(frame, config.main_trend_interval) else ())
            + (*config.trend_intervals, config.entry_interval)
        )
    }


def _condition_statuses(
    frame: MultiTimeframeFrame,
    config: RealtimeStrategyConfig,
) -> list[dict[str, object]]:
    four_hour_interval, one_hour_interval = config.trend_intervals
    four_hour = _build_trend_frame(frame.history(four_hour_interval), config)
    one_hour = _build_trend_frame(frame.history(one_hour_interval), config)
    entry_frame = _build_entry_frame(frame.history(config.entry_interval), config)
    reversal_setup = _build_reversal_setup(
        four_hour_klines=frame.history(four_hour_interval),
        one_hour_klines=frame.history(one_hour_interval),
        entry_klines=frame.history(config.entry_interval),
        config=config,
    )
    if four_hour is None or one_hour is None or entry_frame is None or reversal_setup is None:
        return []

    return [
        *_main_long_conditions(four_hour, one_hour, entry_frame, config),
        *_main_short_conditions(four_hour, one_hour, entry_frame, config),
        *_reversal_long_conditions(four_hour, one_hour, entry_frame, reversal_setup, config),
        *_reversal_short_conditions(four_hour, one_hour, entry_frame, reversal_setup, config),
    ]


def _main_long_conditions(
    four_hour: TrendFrame,
    one_hour: TrendFrame,
    entry_frame: EntryFrame,
    config: RealtimeStrategyConfig,
) -> list[dict[str, object]]:
    entry_price = entry_frame.close
    risk_per_unit = entry_price - entry_frame.recent_swing_low
    risk_reward = (
        config.target_risk_reward
        if risk_per_unit > 0
        else Decimal("0")
    )
    return [
        _condition("主趋势做多", "4h 多头结构", _bullish_structure(four_hour), _structure_detail(four_hour, "UP")),
        _condition("主趋势做多", "4h 多头动能确认", _bullish_momentum(four_hour, config), _momentum_detail(four_hour, config, "UP")),
        _condition("主趋势做多", "1h 多头结构", _bullish_structure(one_hour), _structure_detail(one_hour, "UP")),
        _condition("主趋势做多", "1h 多头动能确认", _bullish_momentum(one_hour, config), _momentum_detail(one_hour, config, "UP")),
        _condition(
            "主趋势做多",
            "15m 回踩到 EMA50 区域",
            _pullback_to_ema50_zone(entry_frame),
            _pullback_zone_detail(entry_frame),
        ),
        _condition(
            "主趋势做多",
            "15m 看涨确认",
            _bullish_confirmation(entry_frame),
            _confirmation_detail(entry_frame, "UP"),
        ),
        _condition(
            "主趋势做多",
            "止损有效",
            risk_per_unit > 0,
            f"entry={_fmt_decimal(entry_price)} > swing_low={_fmt_decimal(entry_frame.recent_swing_low)}",
        ),
        _condition(
            "主趋势做多",
            "风险收益比达标",
            risk_per_unit > 0 and risk_reward >= config.min_risk_reward,
            f"RR={_fmt_decimal(risk_reward)} >= {_fmt_decimal(config.min_risk_reward)}",
        ),
    ]


def _main_short_conditions(
    four_hour: TrendFrame,
    one_hour: TrendFrame,
    entry_frame: EntryFrame,
    config: RealtimeStrategyConfig,
) -> list[dict[str, object]]:
    entry_price = entry_frame.close
    risk_per_unit = entry_frame.recent_swing_high - entry_price
    risk_reward = (
        config.target_risk_reward
        if risk_per_unit > 0
        else Decimal("0")
    )
    return [
        _condition("主趋势做空", "4h 空头结构", _bearish_structure(four_hour), _structure_detail(four_hour, "DOWN")),
        _condition("主趋势做空", "4h 空头动能确认", _bearish_momentum(four_hour, config), _momentum_detail(four_hour, config, "DOWN")),
        _condition("主趋势做空", "1h 空头结构", _bearish_structure(one_hour), _structure_detail(one_hour, "DOWN")),
        _condition("主趋势做空", "1h 空头动能确认", _bearish_momentum(one_hour, config), _momentum_detail(one_hour, config, "DOWN")),
        _condition(
            "主趋势做空",
            "15m 反弹到 EMA50 区域",
            _rebound_to_ema50_zone(entry_frame),
            _rebound_zone_detail(entry_frame),
        ),
        _condition(
            "主趋势做空",
            "15m 看跌确认",
            _bearish_confirmation(entry_frame),
            _confirmation_detail(entry_frame, "DOWN"),
        ),
        _condition(
            "主趋势做空",
            "止损有效",
            risk_per_unit > 0,
            f"entry={_fmt_decimal(entry_price)} < swing_high={_fmt_decimal(entry_frame.recent_swing_high)}",
        ),
        _condition(
            "主趋势做空",
            "风险收益比达标",
            risk_per_unit > 0 and risk_reward >= config.min_risk_reward,
            f"RR={_fmt_decimal(risk_reward)} >= {_fmt_decimal(config.min_risk_reward)}",
        ),
    ]


def _reversal_long_conditions(
    four_hour: TrendFrame,
    one_hour: TrendFrame,
    entry_frame: EntryFrame,
    setup: ReversalSetup,
    config: RealtimeStrategyConfig,
) -> list[dict[str, object]]:
    score = _score_reversal_long(setup)
    chasing = _is_chasing_reversal_long(setup)
    return [
        _condition("趋势转换做多", "4h 下跌趋势", _trend_down(four_hour, config), _trend_detail(four_hour, "DOWN")),
        _condition("趋势转换做多", "1h 上涨趋势", _trend_up(one_hour, config), _trend_detail(one_hour, "UP")),
        _condition("趋势转换做多", "评分达到 70", score >= Decimal("70"), f"score={_fmt_decimal(score)} >= 70"),
        _condition("趋势转换做多", "没有追高", not chasing, _chase_detail(setup.entry_price - setup.ema50_15m, setup)),
        _condition("趋势转换做多", "早期做多条件完整", _early_reversal_long(setup), "early long condition group"),
        _condition("趋势转换做多", "确认做多条件完整", _confirmed_reversal_long(setup), "confirmed long condition group"),
    ]


def _reversal_short_conditions(
    four_hour: TrendFrame,
    one_hour: TrendFrame,
    entry_frame: EntryFrame,
    setup: ReversalSetup,
    config: RealtimeStrategyConfig,
) -> list[dict[str, object]]:
    score = _score_reversal_short(setup)
    chasing = _is_chasing_reversal_short(setup)
    return [
        _condition("趋势转换做空", "4h 上涨趋势", _trend_up(four_hour, config), _trend_detail(four_hour, "UP")),
        _condition("趋势转换做空", "1h 下跌趋势", _trend_down(one_hour, config), _trend_detail(one_hour, "DOWN")),
        _condition("趋势转换做空", "评分达到 70", score >= Decimal("70"), f"score={_fmt_decimal(score)} >= 70"),
        _condition("趋势转换做空", "没有追空", not chasing, _chase_detail(setup.ema50_15m - setup.entry_price, setup)),
        _condition("趋势转换做空", "早期做空条件完整", _early_reversal_short(setup), "early short condition group"),
        _condition("趋势转换做空", "确认做空条件完整", _confirmed_reversal_short(setup), "confirmed short condition group"),
    ]


def _condition(strategy: str, text: str, passed: bool, detail: str) -> dict[str, object]:
    return {
        "strategy": strategy,
        "text": text,
        "passed": passed,
        "detail": detail,
    }


def _nearest_strategy(conditions: list[dict[str, object]]) -> dict[str, object]:
    groups: dict[str, list[dict[str, object]]] = {}
    for condition in conditions:
        groups.setdefault(str(condition["strategy"]), []).append(condition)
    if not groups:
        return {}
    primary_name = _primary_structure_strategy(groups)
    if primary_name is not None:
        name = primary_name
        items = groups[primary_name]
    else:
        name, items = max(
            groups.items(),
            key=lambda item: (sum(1 for condition in item[1] if condition["passed"]), -len(item[1])),
        )
    action_by_name = {
        "主趋势做多": "LONG_ENTRY",
        "主趋势做空": "SHORT_ENTRY",
        "趋势转换做多": "REVERSAL_LONG_ENTRY",
        "趋势转换做空": "REVERSAL_SHORT_ENTRY",
    }
    matched = sum(1 for condition in items if condition["passed"])
    return {
        "name": name,
        "matched": matched,
        "total": len(items),
        "action": action_by_name.get(name, "WAIT"),
    }


def _primary_structure_strategy(groups: dict[str, list[dict[str, object]]]) -> str | None:
    if _condition_passed(groups.get("主趋势做空", []), "4h 空头结构"):
        return "主趋势做空"
    if _condition_passed(groups.get("主趋势做多", []), "4h 多头结构"):
        return "主趋势做多"
    return None


def _condition_passed(conditions: list[dict[str, object]], text: str) -> bool:
    return any(condition.get("text") == text and bool(condition.get("passed")) for condition in conditions)


def _trend_up(frame: TrendFrame, config: RealtimeStrategyConfig) -> bool:
    return (
        frame.close > frame.ema200
        and frame.ema50 > frame.ema200
        and frame.ema50_slope > 0
        and frame.adx >= config.min_adx
        and frame.di_plus > frame.di_minus
    )


def _trend_down(frame: TrendFrame, config: RealtimeStrategyConfig) -> bool:
    return (
        frame.close < frame.ema200
        and frame.ema50 < frame.ema200
        and frame.ema50_slope < 0
        and frame.adx >= config.min_adx
        and frame.di_minus > frame.di_plus
    )


def _bullish_structure(frame: TrendFrame) -> bool:
    return frame.ema50 > frame.ema200


def _bearish_structure(frame: TrendFrame) -> bool:
    return frame.ema50 < frame.ema200


def _bullish_momentum(frame: TrendFrame, config: RealtimeStrategyConfig) -> bool:
    return (
        frame.ema50_slope > 0
        and frame.adx >= config.min_adx
        and frame.di_plus > frame.di_minus
    )


def _bearish_momentum(frame: TrendFrame, config: RealtimeStrategyConfig) -> bool:
    return (
        frame.ema50_slope < 0
        and frame.adx >= config.min_adx
        and frame.di_minus > frame.di_plus
    )


def _structure_detail(frame: TrendFrame, direction: str) -> str:
    if direction == "UP":
        return (
            f"EMA50={_fmt_decimal(frame.ema50)} > EMA200={_fmt_decimal(frame.ema200)}, "
            f"close={_fmt_decimal(frame.close)}"
        )
    return (
        f"EMA50={_fmt_decimal(frame.ema50)} < EMA200={_fmt_decimal(frame.ema200)}, "
        f"close={_fmt_decimal(frame.close)}"
    )


def _momentum_detail(
    frame: TrendFrame,
    config: RealtimeStrategyConfig,
    direction: str,
) -> str:
    if direction == "UP":
        return (
            f"slope={_fmt_decimal(frame.ema50_slope)} > 0, "
            f"ADX={_fmt_decimal(frame.adx)} >= {_fmt_decimal(config.min_adx)}, "
            f"DI+={_fmt_decimal(frame.di_plus)} > DI-={_fmt_decimal(frame.di_minus)}"
        )
    return (
        f"slope={_fmt_decimal(frame.ema50_slope)} < 0, "
        f"ADX={_fmt_decimal(frame.adx)} >= {_fmt_decimal(config.min_adx)}, "
        f"DI-={_fmt_decimal(frame.di_minus)} > DI+={_fmt_decimal(frame.di_plus)}"
    )


def _trend_detail(frame: TrendFrame, direction: str) -> str:
    if direction == "UP":
        return (
            f"close={_fmt_decimal(frame.close)} > EMA200={_fmt_decimal(frame.ema200)}, "
            f"EMA50={_fmt_decimal(frame.ema50)} > EMA200, "
            f"slope={_fmt_decimal(frame.ema50_slope)} > 0, "
            f"ADX={_fmt_decimal(frame.adx)}, DI+={_fmt_decimal(frame.di_plus)} > DI-={_fmt_decimal(frame.di_minus)}"
        )
    return (
        f"close={_fmt_decimal(frame.close)} < EMA200={_fmt_decimal(frame.ema200)}, "
        f"EMA50={_fmt_decimal(frame.ema50)} < EMA200, "
        f"slope={_fmt_decimal(frame.ema50_slope)} < 0, "
        f"ADX={_fmt_decimal(frame.adx)}, DI-={_fmt_decimal(frame.di_minus)} > DI+={_fmt_decimal(frame.di_plus)}"
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


def _pullback_zone_detail(frame: EntryFrame) -> str:
    low = frame.low if frame.low is not None else frame.close
    return (
        f"low={_fmt_decimal(low)} <= EMA50+ATR={_fmt_decimal(frame.ema50 + frame.atr)}, "
        f"close={_fmt_decimal(frame.close)} >= EMA50-ATR={_fmt_decimal(frame.ema50 - frame.atr)}"
    )


def _rebound_zone_detail(frame: EntryFrame) -> str:
    high = frame.high if frame.high is not None else frame.close
    return (
        f"high={_fmt_decimal(high)} >= EMA50-ATR={_fmt_decimal(frame.ema50 - frame.atr)}, "
        f"close={_fmt_decimal(frame.close)} <= EMA50+ATR={_fmt_decimal(frame.ema50 + frame.atr)}"
    )


def _confirmation_detail(frame: EntryFrame, direction: str) -> str:
    if frame.open is not None:
        operator = ">" if direction == "UP" else "<"
        return f"close={_fmt_decimal(frame.close)} {operator} open={_fmt_decimal(frame.open)}"
    operator = ">" if direction == "UP" else "<"
    return f"close={_fmt_decimal(frame.close)} {operator} previous_close={_fmt_decimal(frame.previous_close)}"


def _score_reversal_long(setup: ReversalSetup) -> Decimal:
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


def _score_reversal_short(setup: ReversalSetup) -> Decimal:
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


def _is_chasing_reversal_long(setup: ReversalSetup) -> bool:
    distance = setup.entry_price - setup.ema50_15m
    return distance > setup.atr_15m or _distance_pct(distance, setup.entry_price) > Decimal("0.012")


def _is_chasing_reversal_short(setup: ReversalSetup) -> bool:
    distance = setup.ema50_15m - setup.entry_price
    return distance > setup.atr_15m or _distance_pct(distance, setup.entry_price) > Decimal("0.012")


def _distance_pct(distance: Decimal, entry_price: Decimal) -> Decimal:
    if entry_price == 0:
        return Decimal("0")
    return distance / entry_price


def _chase_detail(distance: Decimal, setup: ReversalSetup) -> str:
    return (
        f"distance={_fmt_decimal(distance)} <= ATR={_fmt_decimal(setup.atr_15m)} "
        f"and pct={_fmt_decimal(_distance_pct(distance, setup.entry_price))} <= 0.012"
    )


def _early_reversal_long(setup: ReversalSetup) -> bool:
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


def _confirmed_reversal_long(setup: ReversalSetup) -> bool:
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


def _early_reversal_short(setup: ReversalSetup) -> bool:
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


def _confirmed_reversal_short(setup: ReversalSetup) -> bool:
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


def _fmt_decimal(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.0001")), "f")
