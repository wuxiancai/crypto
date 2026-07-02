from dataclasses import dataclass, field
from decimal import Decimal

from app.strategy.position_hierarchy import (
    LifecycleState,
    MarketRegime,
    PositionLevel,
    StrategyKernel,
    TradeMode,
)
from app.strategy.signal_router import StrategySignal
from app.strategy.trade_controls import ControlState, build_control_state, tag_market_regime


@dataclass(frozen=True)
class TrendFrame:
    close: Decimal
    fast_ma: Decimal
    slow_ma: Decimal
    fast_ma_slope: Decimal
    adx: Decimal
    di_plus: Decimal
    di_minus: Decimal
    previous_high: Decimal | None = None
    previous_low: Decimal | None = None
    boll_upper: Decimal | None = None
    boll_lower: Decimal | None = None
    boll_middle: Decimal | None = None
    atr: Decimal | None = None


@dataclass(frozen=True)
class WeeklyDailyH4Config:
    min_adx: Decimal = Decimal("18")
    target_risk_reward: Decimal = Decimal("2")
    weekly_risk_pct: Decimal = Decimal("0.006")
    daily_risk_pct: Decimal = Decimal("0.003")
    h4_risk_pct: Decimal = Decimal("0.001")
    weekly_reduction_pct: Decimal = Decimal("0.5")
    min_boll_width_pct: Decimal = Decimal("0.01")
    min_signal_score: Decimal = Decimal("70")
    min_bars_between_trades: int = 3
    daily_exit_policy: str = "FULL_REVERSAL"
    h4_rebound_adx_block_threshold: Decimal | None = Decimal("20")
    stop_atr_multiplier: Decimal = Decimal("1.5")
    max_same_direction_positions_per_level: int = 2
    weekly_max_same_direction_positions: int | None = 2
    daily_max_same_direction_positions: int | None = 1
    h4_max_same_direction_positions: int | None = 2
    allow_same_direction_add_positions: bool = True
    weekly_bear_daily_short_stop_atr_multiplier: Decimal | None = Decimal("2")
    allow_daily_long_entries: bool = False


@dataclass(frozen=True)
class OpenPositionState:
    symbol: str
    side: str
    position_level: PositionLevel
    trade_mode: TradeMode
    lifecycle_state: LifecycleState | str = LifecycleState.OPEN


@dataclass(frozen=True)
class WeeklyDailyH4Input:
    symbol: str
    weekly: TrendFrame
    daily: TrendFrame
    h4: TrendFrame
    open_positions: tuple[OpenPositionState, ...] = ()
    focus_level: PositionLevel | None = None
    bars_since_last_trade: int | None = None
    current_equity: Decimal | None = None
    peak_equity: Decimal | None = None


@dataclass(frozen=True)
class WeeklyDailyH4Decision:
    symbol: str
    signal: StrategySignal
    market_regime: MarketRegime
    control_state: ControlState
    diagnostics: tuple[dict[str, object], ...] = field(default_factory=tuple)


def build_weekly_daily_h4_decision(
    strategy_input: WeeklyDailyH4Input,
    config: WeeklyDailyH4Config | None = None,
) -> WeeklyDailyH4Decision:
    effective_config = config or WeeklyDailyH4Config()
    weekly_regime = tag_market_regime(
        fast_ma=strategy_input.weekly.fast_ma,
        slow_ma=strategy_input.weekly.slow_ma,
        fast_slope=strategy_input.weekly.fast_ma_slope,
        adx=strategy_input.weekly.adx,
        min_adx=effective_config.min_adx,
    )
    daily_regime = tag_market_regime(
        fast_ma=strategy_input.daily.fast_ma,
        slow_ma=strategy_input.daily.slow_ma,
        fast_slope=strategy_input.daily.fast_ma_slope,
        adx=strategy_input.daily.adx,
        min_adx=effective_config.min_adx,
    )
    diagnostics = _base_diagnostics(strategy_input, weekly_regime)

    control_state = _control_state(strategy_input, weekly_regime, effective_config)
    if _should_evaluate_level(strategy_input, PositionLevel.WEEKLY):
        forced_exit = _weekly_forced_exit(strategy_input, weekly_regime)
        if forced_exit is not None:
            return _decision(strategy_input, forced_exit, weekly_regime, control_state, diagnostics)

        staged_reduction = _weekly_staged_reduction(strategy_input, weekly_regime, effective_config, control_state)
        if staged_reduction is not None:
            return _decision(strategy_input, staged_reduction, weekly_regime, control_state, diagnostics)

    if _should_evaluate_level(strategy_input, PositionLevel.DAILY):
        daily_exit = _daily_exit(strategy_input, weekly_regime, effective_config)
        if daily_exit is not None:
            return _decision(strategy_input, daily_exit, weekly_regime, control_state, diagnostics)

    if not control_state.allows_entry:
        return _decision(
            strategy_input,
            _wait([*control_state.reason, "new entries blocked by control layer"], weekly_regime, control_state),
            weekly_regime,
            control_state,
            diagnostics,
        )

    if _should_evaluate_level(strategy_input, PositionLevel.WEEKLY):
        weekly_signal = _weekly_entry(strategy_input, weekly_regime, effective_config, control_state)
        if weekly_signal is not None:
            return _decision(strategy_input, weekly_signal, weekly_regime, control_state, diagnostics)

    if _should_evaluate_level(strategy_input, PositionLevel.DAILY):
        daily_signal = _daily_entry(strategy_input, weekly_regime, effective_config, control_state)
        if daily_signal is not None:
            return _decision(strategy_input, daily_signal, weekly_regime, control_state, diagnostics)

    if _should_evaluate_level(strategy_input, PositionLevel.H4):
        h4_signal = _h4_entry(strategy_input, daily_regime, weekly_regime, effective_config, control_state)
        if h4_signal is not None:
            return _decision(strategy_input, h4_signal, weekly_regime, control_state, diagnostics)

    return _decision(
        strategy_input,
        _wait(["no WEEKLY/DAILY/H4 setup ready"], weekly_regime, control_state),
        weekly_regime,
        control_state,
        diagnostics,
    )


def _weekly_forced_exit(strategy_input: WeeklyDailyH4Input, weekly_regime: MarketRegime) -> StrategySignal | None:
    weekly_position = _open_level(strategy_input, PositionLevel.WEEKLY)
    if weekly_position is None:
        return None
    if weekly_position.side == "SHORT" and weekly_regime == MarketRegime.BULL:
        return _management_signal("EXIT_POSITION", weekly_position.side, PositionLevel.WEEKLY, TradeMode.TREND, Decimal("1"), ["weekly golden cross forced exit"], weekly_regime)
    if weekly_position.side == "LONG" and weekly_regime == MarketRegime.BEAR:
        return _management_signal("EXIT_POSITION", weekly_position.side, PositionLevel.WEEKLY, TradeMode.TREND, Decimal("1"), ["weekly death cross forced exit"], weekly_regime)
    return None


def _weekly_staged_reduction(
    strategy_input: WeeklyDailyH4Input,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
    control_state: ControlState,
) -> StrategySignal | None:
    weekly_position = _open_level(strategy_input, PositionLevel.WEEKLY)
    if weekly_position is None:
        return None
    weekly = strategy_input.weekly
    if weekly_position.side == "SHORT":
        trend_broken = weekly.close > weekly.slow_ma
        structure_broken = weekly.previous_high is not None and weekly.close > weekly.previous_high
        momentum_broken = weekly.di_minus <= weekly.di_plus or weekly.adx < config.min_adx
    else:
        trend_broken = weekly.close < weekly.slow_ma
        structure_broken = weekly.previous_low is not None and weekly.close < weekly.previous_low
        momentum_broken = weekly.di_plus <= weekly.di_minus or weekly.adx < config.min_adx
    broken_stages: list[tuple[str, str]] = []
    if trend_broken:
        broken_stages.append(("REDUCED_TREND", "weekly trend defense broken"))
    if structure_broken:
        broken_stages.append(("REDUCED_STRUCTURE", "weekly structure broken"))
    if momentum_broken:
        broken_stages.append(("REDUCED_MOMENTUM", "weekly momentum broken"))
    if not broken_stages:
        return None
    handled_stages = _lifecycle_stage_set(weekly_position.lifecycle_state)
    new_stages = [(stage, reason) for stage, reason in broken_stages if stage not in handled_stages]
    if not new_stages:
        return _wait(["weekly reduction stages already handled"], weekly_regime, control_state)
    next_lifecycle = _join_lifecycle_stages([*handled_stages, *(stage for stage, _reason in new_stages)])
    return _management_signal(
        "REDUCE_POSITION",
        weekly_position.side,
        PositionLevel.WEEKLY,
        TradeMode.TREND,
        config.weekly_reduction_pct,
        [reason for _stage, reason in new_stages],
        weekly_regime,
        lifecycle_state=next_lifecycle,
    )
    return None


def _weekly_entry(
    strategy_input: WeeklyDailyH4Input,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
    control_state: ControlState,
) -> StrategySignal | None:
    if weekly_regime == MarketRegime.BEAR and _bearish(strategy_input.weekly, config):
        if _has_opposite_level(strategy_input, PositionLevel.WEEKLY, "SHORT"):
            return None
        if _same_direction_limit_reached(strategy_input, PositionLevel.WEEKLY, "SHORT", config):
            return _wait(["same direction additions disabled for WEEKLY"], weekly_regime, control_state)
        return _entry_signal(
            side="SHORT",
            level=PositionLevel.WEEKLY,
            mode=TradeMode.TREND,
            frame=strategy_input.weekly,
            risk_pct=config.weekly_risk_pct,
            reason=["weekly bear trend"],
            weekly_regime=weekly_regime,
            control_state=control_state,
            config=config,
        )
    if weekly_regime == MarketRegime.BULL and _bullish(strategy_input.weekly, config):
        if _has_opposite_level(strategy_input, PositionLevel.WEEKLY, "LONG"):
            return None
        if _same_direction_limit_reached(strategy_input, PositionLevel.WEEKLY, "LONG", config):
            return _wait(["same direction additions disabled for WEEKLY"], weekly_regime, control_state)
        return _entry_signal(
            side="LONG",
            level=PositionLevel.WEEKLY,
            mode=TradeMode.TREND,
            frame=strategy_input.weekly,
            risk_pct=config.weekly_risk_pct,
            reason=["weekly bull trend"],
            weekly_regime=weekly_regime,
            control_state=control_state,
            config=config,
        )
    return None


def _daily_entry(
    strategy_input: WeeklyDailyH4Input,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
    control_state: ControlState,
) -> StrategySignal | None:
    if _bullish(strategy_input.daily, config):
        if not config.allow_daily_long_entries:
            return _wait(["daily long entries disabled"], weekly_regime, control_state)
        if _has_opposite_level(strategy_input, PositionLevel.DAILY, "LONG"):
            return None
        if _same_direction_limit_reached(strategy_input, PositionLevel.DAILY, "LONG", config):
            return _wait(["same direction position limit reached for DAILY"], weekly_regime, control_state)
        mode = TradeMode.TREND
        return _entry_signal(
            "LONG",
            PositionLevel.DAILY,
            mode,
            strategy_input.daily,
            config.daily_risk_pct,
            ["daily independent long trend"],
            weekly_regime,
            control_state,
            config,
        )
    if _bearish(strategy_input.daily, config):
        if _has_opposite_level(strategy_input, PositionLevel.DAILY, "SHORT"):
            return None
        if _same_direction_limit_reached(strategy_input, PositionLevel.DAILY, "SHORT", config):
            return _wait(["same direction position limit reached for DAILY"], weekly_regime, control_state)
        mode = TradeMode.TREND
        return _entry_signal(
            "SHORT",
            PositionLevel.DAILY,
            mode,
            strategy_input.daily,
            config.daily_risk_pct,
            ["daily independent short trend"],
            weekly_regime,
            control_state,
            config,
        )
    return None


def _h4_entry(
    strategy_input: WeeklyDailyH4Input,
    daily_regime: MarketRegime,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
    control_state: ControlState,
) -> StrategySignal | None:
    if not _h4_volatility_open(strategy_input.h4, config):
        return None
    if _bullish(strategy_input.h4, config):
        if _has_opposite_level(strategy_input, PositionLevel.H4, "LONG"):
            return None
        if _same_direction_limit_reached(strategy_input, PositionLevel.H4, "LONG", config):
            return _wait(["same direction additions disabled for H4"], weekly_regime, control_state)
        mode = TradeMode.TREND
        if _h4_breakout(strategy_input.h4):
            mode = TradeMode.BREAKOUT
            reason = "h4 independent long breakout"
        else:
            reason = "h4 independent long trend"
        return _entry_signal(
            "LONG",
            PositionLevel.H4,
            mode,
            strategy_input.h4,
            config.h4_risk_pct,
            [reason],
            weekly_regime,
            control_state,
            config,
        )
    if _bearish(strategy_input.h4, config):
        if _has_opposite_level(strategy_input, PositionLevel.H4, "SHORT"):
            return None
        if _same_direction_limit_reached(strategy_input, PositionLevel.H4, "SHORT", config):
            return _wait(["same direction additions disabled for H4"], weekly_regime, control_state)
        mode = TradeMode.TREND
        if _h4_breakdown(strategy_input.h4):
            mode = TradeMode.BREAKOUT
            reason = "h4 independent short breakout"
        else:
            reason = "h4 independent short trend"
        return _entry_signal(
            "SHORT",
            PositionLevel.H4,
            mode,
            strategy_input.h4,
            config.h4_risk_pct,
            [reason],
            weekly_regime,
            control_state,
            config,
        )
    return None


def _relative_trade_mode(side: str, upper_regime: MarketRegime) -> TradeMode:
    if side == "LONG" and upper_regime == MarketRegime.BULL:
        return TradeMode.TREND
    if side == "SHORT" and upper_regime == MarketRegime.BEAR:
        return TradeMode.TREND
    if upper_regime in {MarketRegime.BULL, MarketRegime.BEAR}:
        return TradeMode.REBOUND
    return TradeMode.TREND


def _relative_reason(prefix: str, mode: TradeMode, upper_regime: MarketRegime) -> str:
    if mode == TradeMode.REBOUND:
        return f"{prefix} rebound under weekly {upper_regime.value.lower()}"
    if upper_regime in {MarketRegime.BULL, MarketRegime.BEAR}:
        return f"{prefix} trend with weekly {upper_regime.value.lower()}"
    return f"{prefix} neutral upper timeframe"


def _daily_exit(
    strategy_input: WeeklyDailyH4Input,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
) -> StrategySignal | None:
    if config.daily_exit_policy.upper() != "FULL_REVERSAL":
        return None
    daily_position = _open_level(strategy_input, PositionLevel.DAILY)
    if daily_position is None:
        return None
    daily = strategy_input.daily
    if daily_position.side == "LONG" and _bearish(daily, config):
        return _management_signal(
            "EXIT_POSITION",
            "LONG",
            PositionLevel.DAILY,
            daily_position.trade_mode,
            Decimal("1"),
            ["daily full bearish reversal"],
            weekly_regime,
        )
    if daily_position.side == "SHORT" and _bullish(daily, config):
        return _management_signal(
            "EXIT_POSITION",
            "SHORT",
            PositionLevel.DAILY,
            daily_position.trade_mode,
            Decimal("1"),
            ["daily full bullish reversal"],
            weekly_regime,
        )
    return None


def _counter_rebound_blocked(mode: TradeMode, upper_frame: TrendFrame, config: WeeklyDailyH4Config) -> bool:
    threshold = config.h4_rebound_adx_block_threshold
    return mode == TradeMode.REBOUND and threshold is not None and upper_frame.adx >= threshold


def _entry_signal(
    side: str,
    level: PositionLevel,
    mode: TradeMode,
    frame: TrendFrame,
    risk_pct: Decimal,
    reason: list[str],
    weekly_regime: MarketRegime,
    control_state: ControlState,
    config: WeeklyDailyH4Config,
) -> StrategySignal:
    entry_price = frame.close
    atr_value = frame.atr or abs(frame.fast_ma - frame.slow_ma) or entry_price * Decimal("0.02")
    stop_atr_multiplier = _stop_atr_multiplier_for_entry(side, level, weekly_regime, config)
    stop_atr_distance = atr_value * stop_atr_multiplier
    if side == "LONG":
        if level == PositionLevel.WEEKLY:
            stop_loss = frame.slow_ma if frame.slow_ma < entry_price else entry_price - atr_value
        else:
            structure_stop = min(frame.previous_low or entry_price - atr_value, entry_price - atr_value)
            stop_loss = max(structure_stop, entry_price - stop_atr_distance)
        take_profit = entry_price + (entry_price - stop_loss) * config.target_risk_reward
        action = "LONG_ENTRY"
    else:
        if level == PositionLevel.WEEKLY:
            stop_loss = frame.slow_ma if frame.slow_ma > entry_price else entry_price + atr_value
        else:
            structure_stop = max(frame.previous_high or entry_price + atr_value, entry_price + atr_value)
            stop_loss = min(structure_stop, entry_price + stop_atr_distance)
        take_profit = entry_price - (stop_loss - entry_price) * config.target_risk_reward
        action = "SHORT_ENTRY"
    return StrategySignal(
        action=action,
        strategy_type=f"{level.value}_{side}_{mode.value}",
        bucket=level.value,
        reason=reason,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=config.target_risk_reward,
        risk_pct=risk_pct,
        score=control_state.signal_score.total,
        trailing_atr=atr_value,
        strategy_kernel=StrategyKernel.WEEKLY_DAILY_H4_V1.value,
        position_level=level.value,
        trade_mode=mode.value,
        market_regime=weekly_regime.value,
        lifecycle_state=LifecycleState.PLANNED.value,
    )


def _management_signal(
    action: str,
    side: str,
    level: PositionLevel,
    mode: TradeMode,
    reduce_pct: Decimal,
    reason: list[str],
    weekly_regime: MarketRegime,
    lifecycle_state: str | None = None,
) -> StrategySignal:
    return StrategySignal(
        action=action,
        strategy_type=f"{level.value}_{side}_{mode.value}",
        bucket=level.value,
        reason=reason,
        strategy_kernel=StrategyKernel.WEEKLY_DAILY_H4_V1.value,
        position_level=level.value,
        trade_mode=mode.value,
        market_regime=weekly_regime.value,
        lifecycle_state=lifecycle_state
        or (LifecycleState.EXITING.value if action == "EXIT_POSITION" else LifecycleState.REDUCING.value),
        reduce_pct=reduce_pct,
    )


def _stop_atr_multiplier_for_entry(
    side: str,
    level: PositionLevel,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
) -> Decimal:
    if (
        level == PositionLevel.DAILY
        and side == "SHORT"
        and weekly_regime == MarketRegime.BEAR
        and config.weekly_bear_daily_short_stop_atr_multiplier is not None
    ):
        return config.weekly_bear_daily_short_stop_atr_multiplier
    return config.stop_atr_multiplier


def _wait(reason: list[str], weekly_regime: MarketRegime, control_state: ControlState) -> StrategySignal:
    return StrategySignal(
        action="WAIT",
        strategy_type="SYSTEM",
        reason=reason,
        strategy_kernel=StrategyKernel.WEEKLY_DAILY_H4_V1.value,
        market_regime=weekly_regime.value,
        score=control_state.signal_score.total,
    )


def _decision(
    strategy_input: WeeklyDailyH4Input,
    signal: StrategySignal,
    weekly_regime: MarketRegime,
    control_state: ControlState,
    diagnostics: tuple[dict[str, object], ...],
) -> WeeklyDailyH4Decision:
    return WeeklyDailyH4Decision(
        symbol=strategy_input.symbol,
        signal=signal,
        market_regime=weekly_regime,
        control_state=control_state,
        diagnostics=diagnostics,
    )


def _control_state(
    strategy_input: WeeklyDailyH4Input,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
) -> ControlState:
    trend_alignment = weekly_regime in {MarketRegime.BEAR, MarketRegime.BULL}
    h4 = strategy_input.h4
    structure_confirmation = _h4_breakout(h4) or _h4_breakdown(h4) or h4.close != h4.fast_ma
    momentum_confirmation = (h4.di_plus != h4.di_minus) and h4.adx >= config.min_adx
    volatility_expansion = _h4_volatility_open(h4, config)
    return build_control_state(
        market_regime=weekly_regime,
        bars_since_last_trade=strategy_input.bars_since_last_trade,
        min_bars_between_trades=config.min_bars_between_trades,
        current_equity=strategy_input.current_equity,
        peak_equity=strategy_input.peak_equity,
        trend_alignment=trend_alignment,
        structure_confirmation=structure_confirmation,
        momentum_confirmation=momentum_confirmation,
        volatility_expansion=volatility_expansion,
    )


def _base_diagnostics(strategy_input: WeeklyDailyH4Input, weekly_regime: MarketRegime) -> tuple[dict[str, object], ...]:
    return (
        {"strategy": "WEEKLY", "text": "周线环境", "passed": weekly_regime in {MarketRegime.BULL, MarketRegime.BEAR}, "detail": weekly_regime.value, "required": True},
        {"strategy": "DAILY", "text": "日线战术层互斥", "passed": _open_level(strategy_input, PositionLevel.DAILY) is None, "detail": "no daily position" if _open_level(strategy_input, PositionLevel.DAILY) is None else "daily position already open", "required": True},
        {"strategy": "H4", "text": "4H 执行层", "passed": True, "detail": "breakout/pullback/continuation only", "required": True},
    )


def _open_level(strategy_input: WeeklyDailyH4Input, level: PositionLevel) -> OpenPositionState | None:
    for position in strategy_input.open_positions:
        if position.position_level == level:
            return position
    return None


def _has_opposite_level(strategy_input: WeeklyDailyH4Input, level: PositionLevel, side: str) -> bool:
    return any(position.position_level == level and position.side != side for position in strategy_input.open_positions)


def _same_direction_count(strategy_input: WeeklyDailyH4Input, level: PositionLevel, side: str) -> int:
    return sum(1 for position in strategy_input.open_positions if position.position_level == level and position.side == side)


def _same_direction_limit_reached(
    strategy_input: WeeklyDailyH4Input,
    level: PositionLevel,
    side: str,
    config: WeeklyDailyH4Config,
) -> bool:
    level_limit = {
        PositionLevel.WEEKLY: config.weekly_max_same_direction_positions,
        PositionLevel.DAILY: config.daily_max_same_direction_positions,
        PositionLevel.H4: config.h4_max_same_direction_positions,
    }[level]
    limit = 1 if not config.allow_same_direction_add_positions else (
        level_limit if level_limit is not None else config.max_same_direction_positions_per_level
    )
    return _same_direction_count(strategy_input, level, side) >= limit


def _should_evaluate_level(strategy_input: WeeklyDailyH4Input, level: PositionLevel) -> bool:
    return strategy_input.focus_level is None or strategy_input.focus_level == level


def _lifecycle_stage_set(lifecycle_state: LifecycleState | str | None) -> tuple[str, ...]:
    if lifecycle_state is None:
        return ()
    value = lifecycle_state.value if isinstance(lifecycle_state, LifecycleState) else str(lifecycle_state)
    return tuple(part for part in value.split("|") if part.startswith("REDUCED_"))


def _join_lifecycle_stages(stages: list[str] | tuple[str, ...]) -> str:
    ordered = []
    for stage in ("REDUCED_TREND", "REDUCED_STRUCTURE", "REDUCED_MOMENTUM"):
        if stage in stages:
            ordered.append(stage)
    return "|".join(ordered) if ordered else LifecycleState.REDUCING.value


def _bullish(frame: TrendFrame, config: WeeklyDailyH4Config) -> bool:
    return frame.fast_ma > frame.slow_ma and frame.fast_ma_slope > 0 and frame.adx >= config.min_adx and frame.di_plus > frame.di_minus


def _bearish(frame: TrendFrame, config: WeeklyDailyH4Config) -> bool:
    return frame.fast_ma < frame.slow_ma and frame.fast_ma_slope < 0 and frame.adx >= config.min_adx and frame.di_minus > frame.di_plus


def _h4_volatility_open(frame: TrendFrame, config: WeeklyDailyH4Config) -> bool:
    if frame.boll_upper is None or frame.boll_lower is None or frame.boll_middle is None or frame.boll_middle <= 0:
        return True
    return (frame.boll_upper - frame.boll_lower) / frame.boll_middle >= config.min_boll_width_pct


def _h4_breakout(frame: TrendFrame) -> bool:
    return frame.previous_high is not None and frame.close > frame.previous_high


def _h4_breakdown(frame: TrendFrame) -> bool:
    return frame.previous_low is not None and frame.close < frame.previous_low
