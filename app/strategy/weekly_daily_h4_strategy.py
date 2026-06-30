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


@dataclass(frozen=True)
class OpenPositionState:
    symbol: str
    side: str
    position_level: PositionLevel
    trade_mode: TradeMode
    lifecycle_state: LifecycleState = LifecycleState.OPEN


@dataclass(frozen=True)
class WeeklyDailyH4Input:
    symbol: str
    weekly: TrendFrame
    daily: TrendFrame
    h4: TrendFrame
    open_positions: tuple[OpenPositionState, ...] = ()
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
    diagnostics = _base_diagnostics(strategy_input, weekly_regime)

    forced_exit = _weekly_forced_exit(strategy_input, weekly_regime)
    control_state = _control_state(strategy_input, weekly_regime, effective_config)
    if forced_exit is not None:
        return _decision(strategy_input, forced_exit, weekly_regime, control_state, diagnostics)

    staged_reduction = _weekly_staged_reduction(strategy_input, weekly_regime, effective_config)
    if staged_reduction is not None:
        return _decision(strategy_input, staged_reduction, weekly_regime, control_state, diagnostics)

    if not control_state.allows_entry:
        return _decision(
            strategy_input,
            _wait([*control_state.reason, "new entries blocked by control layer"], weekly_regime, control_state),
            weekly_regime,
            control_state,
            diagnostics,
        )

    weekly_signal = _weekly_entry(strategy_input, weekly_regime, effective_config, control_state)
    if weekly_signal is not None:
        return _decision(strategy_input, weekly_signal, weekly_regime, control_state, diagnostics)

    daily_signal = _daily_entry(strategy_input, weekly_regime, effective_config, control_state)
    if daily_signal is not None:
        return _decision(strategy_input, daily_signal, weekly_regime, control_state, diagnostics)

    h4_signal = _h4_entry(strategy_input, weekly_regime, effective_config, control_state)
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
    if trend_broken or structure_broken or momentum_broken:
        reasons = []
        if trend_broken:
            reasons.append("weekly trend defense broken")
        if structure_broken:
            reasons.append("weekly structure broken")
        if momentum_broken:
            reasons.append("weekly momentum broken")
        return _management_signal("REDUCE_POSITION", weekly_position.side, PositionLevel.WEEKLY, TradeMode.TREND, config.weekly_reduction_pct, reasons, weekly_regime)
    return None


def _weekly_entry(
    strategy_input: WeeklyDailyH4Input,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
    control_state: ControlState,
) -> StrategySignal | None:
    if _open_level(strategy_input, PositionLevel.WEEKLY) is not None:
        return None
    if weekly_regime == MarketRegime.BEAR and _bearish(strategy_input.daily, config):
        return _entry_signal(
            side="SHORT",
            level=PositionLevel.WEEKLY,
            mode=TradeMode.TREND,
            frame=strategy_input.h4,
            risk_pct=config.weekly_risk_pct,
            reason=["weekly bear environment", "daily death-cross confirmation"],
            weekly_regime=weekly_regime,
            control_state=control_state,
        )
    if weekly_regime == MarketRegime.BULL and _bullish(strategy_input.daily, config):
        return _entry_signal(
            side="LONG",
            level=PositionLevel.WEEKLY,
            mode=TradeMode.TREND,
            frame=strategy_input.h4,
            risk_pct=config.weekly_risk_pct,
            reason=["weekly bull environment", "daily golden-cross confirmation"],
            weekly_regime=weekly_regime,
            control_state=control_state,
        )
    return None


def _daily_entry(
    strategy_input: WeeklyDailyH4Input,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
    control_state: ControlState,
) -> StrategySignal | None:
    if _open_level(strategy_input, PositionLevel.DAILY) is not None:
        return None
    if weekly_regime == MarketRegime.BEAR:
        if _bullish(strategy_input.daily, config) and _bullish(strategy_input.h4, config):
            return _entry_signal("LONG", PositionLevel.DAILY, TradeMode.REBOUND, strategy_input.h4, config.daily_risk_pct, ["daily rebound under weekly bear"], weekly_regime, control_state)
        if _bearish(strategy_input.daily, config) and _bearish(strategy_input.h4, config):
            return _entry_signal("SHORT", PositionLevel.DAILY, TradeMode.TREND, strategy_input.h4, config.daily_risk_pct, ["daily trend short under weekly bear"], weekly_regime, control_state)
    if weekly_regime == MarketRegime.BULL:
        if _bearish(strategy_input.daily, config) and _bearish(strategy_input.h4, config):
            return _entry_signal("SHORT", PositionLevel.DAILY, TradeMode.REBOUND, strategy_input.h4, config.daily_risk_pct, ["daily pullback short under weekly bull"], weekly_regime, control_state)
        if _bullish(strategy_input.daily, config) and _bullish(strategy_input.h4, config):
            return _entry_signal("LONG", PositionLevel.DAILY, TradeMode.TREND, strategy_input.h4, config.daily_risk_pct, ["daily trend long under weekly bull"], weekly_regime, control_state)
    return None


def _h4_entry(
    strategy_input: WeeklyDailyH4Input,
    weekly_regime: MarketRegime,
    config: WeeklyDailyH4Config,
    control_state: ControlState,
) -> StrategySignal | None:
    if _open_level(strategy_input, PositionLevel.H4) is not None:
        return None
    if not _h4_volatility_open(strategy_input.h4, config):
        return None
    if weekly_regime == MarketRegime.BEAR:
        if _h4_breakdown(strategy_input.h4) and _bearish(strategy_input.h4, config):
            return _entry_signal("SHORT", PositionLevel.H4, TradeMode.BREAKOUT, strategy_input.h4, config.h4_risk_pct, ["h4 breakdown breakout under weekly bear"], weekly_regime, control_state)
        if _bearish(strategy_input.h4, config):
            return _entry_signal("SHORT", PositionLevel.H4, TradeMode.CONTINUATION, strategy_input.h4, config.h4_risk_pct, ["h4 continuation under weekly bear"], weekly_regime, control_state)
    if weekly_regime == MarketRegime.BULL:
        if _h4_breakout(strategy_input.h4) and _bullish(strategy_input.h4, config):
            return _entry_signal("LONG", PositionLevel.H4, TradeMode.BREAKOUT, strategy_input.h4, config.h4_risk_pct, ["h4 breakout under weekly bull"], weekly_regime, control_state)
        if _bullish(strategy_input.h4, config):
            return _entry_signal("LONG", PositionLevel.H4, TradeMode.CONTINUATION, strategy_input.h4, config.h4_risk_pct, ["h4 continuation under weekly bull"], weekly_regime, control_state)
    return None


def _entry_signal(
    side: str,
    level: PositionLevel,
    mode: TradeMode,
    frame: TrendFrame,
    risk_pct: Decimal,
    reason: list[str],
    weekly_regime: MarketRegime,
    control_state: ControlState,
) -> StrategySignal:
    entry_price = frame.close
    atr_value = frame.atr or abs(frame.fast_ma - frame.slow_ma) or entry_price * Decimal("0.02")
    if side == "LONG":
        stop_loss = min(frame.previous_low or entry_price - atr_value, entry_price - atr_value)
        take_profit = entry_price + (entry_price - stop_loss) * Decimal("2")
        action = "LONG_ENTRY"
    else:
        stop_loss = max(frame.previous_high or entry_price + atr_value, entry_price + atr_value)
        take_profit = entry_price - (stop_loss - entry_price) * Decimal("2")
        action = "SHORT_ENTRY"
    return StrategySignal(
        action=action,
        strategy_type=f"{level.value}_{side}_{mode.value}",
        bucket=level.value,
        reason=reason,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=Decimal("2"),
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
        lifecycle_state=LifecycleState.EXITING.value if action == "EXIT_POSITION" else LifecycleState.REDUCING.value,
        reduce_pct=reduce_pct,
    )


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
