from dataclasses import dataclass, field
from decimal import Decimal

from app.strategy.signal_router import StrategySignal


SHORT_DAY_CORE = "SHORT_DAY_CORE"
SHORT_4H_1H_ADDON = "SHORT_4H_1H_ADDON"
LONG_4H_HEDGE = "LONG_4H_HEDGE"
LONG_DAY_CORE = "LONG_DAY_CORE"
LONG_4H_1H_ADDON = "LONG_4H_1H_ADDON"
SHORT_4H_HEDGE = "SHORT_4H_HEDGE"

DAY_CORE = "DAY_CORE"
FOUR_HOUR_ADDON = "FOUR_HOUR_ADDON"
FOUR_HOUR_HEDGE = "FOUR_HOUR_HEDGE"


@dataclass(frozen=True)
class LayeredStrategyConfig:
    min_adx: Decimal = Decimal("20")
    target_risk_reward: Decimal = Decimal("2")
    core_risk_pct: Decimal = Decimal("0.005")
    addon_risk_pct: Decimal = Decimal("0.003")
    hedge_risk_pct: Decimal = Decimal("0.002")


@dataclass(frozen=True)
class TrendSnapshot:
    close: Decimal
    fast_ma: Decimal
    slow_ma: Decimal
    fast_ma_slope: Decimal
    adx: Decimal
    di_plus: Decimal
    di_minus: Decimal


@dataclass(frozen=True)
class LayeredEntryFrame:
    close: Decimal
    open: Decimal
    high: Decimal
    low: Decimal
    fast_ma: Decimal
    atr: Decimal
    recent_swing_low: Decimal
    recent_swing_high: Decimal


@dataclass(frozen=True)
class LayeredStrategyInput:
    symbol: str
    daily: TrendSnapshot
    four_hour: TrendSnapshot
    one_hour: TrendSnapshot
    entry: LayeredEntryFrame


@dataclass(frozen=True)
class LayeredStrategyDecision:
    symbol: str
    signal: StrategySignal | None
    candidates: tuple[str, ...] = ()
    diagnostics: tuple[dict[str, object], ...] = field(default_factory=tuple)


def build_layered_strategy_decision(
    strategy_input: LayeredStrategyInput,
    config: LayeredStrategyConfig | None = None,
) -> LayeredStrategyDecision:
    effective_config = config or LayeredStrategyConfig()
    candidates: list[str] = []
    diagnostics: list[dict[str, object]] = []

    daily_short = _bearish(strategy_input.daily, effective_config)
    daily_long = _bullish(strategy_input.daily, effective_config)
    four_hour_short = _bearish(strategy_input.four_hour, effective_config)
    four_hour_long = _bullish(strategy_input.four_hour, effective_config)
    one_hour_short = _bearish(strategy_input.one_hour, effective_config)
    one_hour_long = _bullish(strategy_input.one_hour, effective_config)

    signal: StrategySignal | None = None
    if daily_short:
        candidates.append(SHORT_DAY_CORE)
        diagnostics.append(_diagnostic(SHORT_DAY_CORE, True, ["daily bearish"]))
        signal = _short_signal(
            strategy_type=SHORT_DAY_CORE,
            bucket=DAY_CORE,
            entry=strategy_input.entry,
            risk_pct=effective_config.core_risk_pct,
            config=effective_config,
            reason=["daily bearish core", "15m bearish entry"],
        )
        if four_hour_short and one_hour_short:
            candidates.append(SHORT_4H_1H_ADDON)
            diagnostics.append(_diagnostic(SHORT_4H_1H_ADDON, True, ["4h/1h bearish"]))
        if four_hour_long and one_hour_long:
            candidates.append(LONG_4H_HEDGE)
            diagnostics.append(_diagnostic(LONG_4H_HEDGE, True, ["daily bearish", "4h/1h bullish rebound"]))
            hedge_signal = _long_signal(
                strategy_type=LONG_4H_HEDGE,
                bucket=FOUR_HOUR_HEDGE,
                entry=strategy_input.entry,
                risk_pct=effective_config.hedge_risk_pct,
                config=effective_config,
                reason=["daily bearish", "4h/1h bullish hedge"],
            )
            if hedge_signal is not None:
                signal = hedge_signal
    elif daily_long:
        candidates.append(LONG_DAY_CORE)
        diagnostics.append(_diagnostic(LONG_DAY_CORE, True, ["daily bullish"]))
        signal = _long_signal(
            strategy_type=LONG_DAY_CORE,
            bucket=DAY_CORE,
            entry=strategy_input.entry,
            risk_pct=effective_config.core_risk_pct,
            config=effective_config,
            reason=["daily bullish core", "15m bullish entry"],
        )
        if four_hour_long and one_hour_long:
            candidates.append(LONG_4H_1H_ADDON)
            diagnostics.append(_diagnostic(LONG_4H_1H_ADDON, True, ["4h/1h bullish"]))
        if four_hour_short and one_hour_short:
            candidates.append(SHORT_4H_HEDGE)
            diagnostics.append(_diagnostic(SHORT_4H_HEDGE, True, ["daily bullish", "4h/1h bearish pullback"]))
            hedge_signal = _short_signal(
                strategy_type=SHORT_4H_HEDGE,
                bucket=FOUR_HOUR_HEDGE,
                entry=strategy_input.entry,
                risk_pct=effective_config.hedge_risk_pct,
                config=effective_config,
                reason=["daily bullish", "4h/1h bearish hedge"],
            )
            if hedge_signal is not None:
                signal = hedge_signal
    else:
        diagnostics.append(_diagnostic("DAY_CORE", False, ["daily trend unclear"]))

    return LayeredStrategyDecision(
        symbol=strategy_input.symbol,
        signal=signal,
        candidates=tuple(candidates),
        diagnostics=tuple(diagnostics),
    )


def _bullish(snapshot: TrendSnapshot, config: LayeredStrategyConfig) -> bool:
    return (
        snapshot.fast_ma > snapshot.slow_ma
        and snapshot.fast_ma_slope > 0
        and snapshot.adx >= config.min_adx
        and snapshot.di_plus > snapshot.di_minus
    )


def _bearish(snapshot: TrendSnapshot, config: LayeredStrategyConfig) -> bool:
    return (
        snapshot.fast_ma < snapshot.slow_ma
        and snapshot.fast_ma_slope < 0
        and snapshot.adx >= config.min_adx
        and snapshot.di_minus > snapshot.di_plus
    )


def _long_signal(
    strategy_type: str,
    bucket: str,
    entry: LayeredEntryFrame,
    risk_pct: Decimal,
    config: LayeredStrategyConfig,
    reason: list[str],
) -> StrategySignal | None:
    risk_per_unit = entry.close - entry.recent_swing_low
    if risk_per_unit <= 0:
        return None
    take_profit = entry.close + risk_per_unit * config.target_risk_reward
    return StrategySignal(
        action="LONG_ENTRY",
        strategy_type=strategy_type,
        bucket=bucket,
        entry_price=entry.close,
        stop_loss=entry.recent_swing_low,
        take_profit=take_profit,
        risk_reward=config.target_risk_reward,
        risk_pct=risk_pct,
        reason=reason,
    )


def _short_signal(
    strategy_type: str,
    bucket: str,
    entry: LayeredEntryFrame,
    risk_pct: Decimal,
    config: LayeredStrategyConfig,
    reason: list[str],
) -> StrategySignal | None:
    risk_per_unit = entry.recent_swing_high - entry.close
    if risk_per_unit <= 0:
        return None
    take_profit = entry.close - risk_per_unit * config.target_risk_reward
    return StrategySignal(
        action="SHORT_ENTRY",
        strategy_type=strategy_type,
        bucket=bucket,
        entry_price=entry.close,
        stop_loss=entry.recent_swing_high,
        take_profit=take_profit,
        risk_reward=config.target_risk_reward,
        risk_pct=risk_pct,
        reason=reason,
    )


def _diagnostic(strategy_type: str, passed: bool, detail: list[str]) -> dict[str, object]:
    text_by_strategy = {
        "DAY_CORE": "日线趋势明确",
        SHORT_DAY_CORE: "日线空头主趋势",
        LONG_DAY_CORE: "日线多头主趋势",
        SHORT_4H_1H_ADDON: "4h/1h 空头顺势加仓",
        LONG_4H_1H_ADDON: "4h/1h 多头顺势加仓",
        SHORT_4H_HEDGE: "4h 空头对冲",
        LONG_4H_HEDGE: "4h 多头对冲",
    }
    return {
        "strategy": strategy_type,
        "strategy_type": strategy_type,
        "text": text_by_strategy.get(strategy_type, strategy_type),
        "passed": passed,
        "detail": "; ".join(detail),
    }

