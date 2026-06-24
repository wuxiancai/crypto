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
class TrendRegime:
    direction: str
    confirmed_at_ms: int | None = None


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
    daily_regime: TrendRegime | None = None
    four_hour_regime: TrendRegime | None = None
    one_hour_regime: TrendRegime | None = None


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

    daily_short = _regime_direction(strategy_input.daily_regime) == "SHORT" or (
        strategy_input.daily_regime is None and _bearish(strategy_input.daily, effective_config)
    )
    daily_long = _regime_direction(strategy_input.daily_regime) == "LONG" or (
        strategy_input.daily_regime is None and _bullish(strategy_input.daily, effective_config)
    )
    four_hour_short = _regime_direction(strategy_input.four_hour_regime) == "SHORT" or (
        strategy_input.four_hour_regime is None and _bearish(strategy_input.four_hour, effective_config)
    )
    four_hour_long = _regime_direction(strategy_input.four_hour_regime) == "LONG" or (
        strategy_input.four_hour_regime is None and _bullish(strategy_input.four_hour, effective_config)
    )
    one_hour_short = _regime_direction(strategy_input.one_hour_regime) == "SHORT" or (
        strategy_input.one_hour_regime is None and _bearish(strategy_input.one_hour, effective_config)
    )
    one_hour_long = _regime_direction(strategy_input.one_hour_regime) == "LONG" or (
        strategy_input.one_hour_regime is None and _bullish(strategy_input.one_hour, effective_config)
    )

    signal: StrategySignal | None = None
    if daily_short:
        candidates.append(SHORT_DAY_CORE)
        diagnostics.extend(
            _core_strategy_diagnostics(
                SHORT_DAY_CORE,
                strategy_input,
                "DOWN",
                effective_config,
            )
        )
        if four_hour_short and one_hour_short and _bearish_entry(strategy_input.entry):
            signal = _short_signal(
                strategy_type=SHORT_DAY_CORE,
                bucket=DAY_CORE,
                entry=strategy_input.entry,
                risk_pct=effective_config.core_risk_pct,
                config=effective_config,
                reason=["daily bearish core", "4h/1h bearish", "15m bearish entry"],
            )
        if four_hour_short and one_hour_short:
            candidates.append(SHORT_4H_1H_ADDON)
            diagnostics.extend(_trend_diagnostics(SHORT_4H_1H_ADDON, "4h 空头", strategy_input.four_hour, "DOWN", effective_config, strategy_input.four_hour_regime))
            diagnostics.extend(_trend_diagnostics(SHORT_4H_1H_ADDON, "1h 空头", strategy_input.one_hour, "DOWN", effective_config, strategy_input.one_hour_regime))
        if four_hour_long and one_hour_long:
            candidates.append(LONG_4H_HEDGE)
            diagnostics.extend(_trend_diagnostics(LONG_4H_HEDGE, "日线空头", strategy_input.daily, "DOWN", effective_config, strategy_input.daily_regime))
            diagnostics.extend(_trend_diagnostics(LONG_4H_HEDGE, "4h 多头", strategy_input.four_hour, "UP", effective_config, strategy_input.four_hour_regime))
            diagnostics.extend(_trend_diagnostics(LONG_4H_HEDGE, "1h 多头", strategy_input.one_hour, "UP", effective_config, strategy_input.one_hour_regime))
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
        diagnostics.extend(
            _core_strategy_diagnostics(
                LONG_DAY_CORE,
                strategy_input,
                "UP",
                effective_config,
            )
        )
        if four_hour_long and one_hour_long and _bullish_entry(strategy_input.entry):
            signal = _long_signal(
                strategy_type=LONG_DAY_CORE,
                bucket=DAY_CORE,
                entry=strategy_input.entry,
                risk_pct=effective_config.core_risk_pct,
                config=effective_config,
                reason=["daily bullish core", "4h/1h bullish", "15m bullish entry"],
            )
        if four_hour_long and one_hour_long:
            candidates.append(LONG_4H_1H_ADDON)
            diagnostics.extend(_trend_diagnostics(LONG_4H_1H_ADDON, "4h 多头", strategy_input.four_hour, "UP", effective_config, strategy_input.four_hour_regime))
            diagnostics.extend(_trend_diagnostics(LONG_4H_1H_ADDON, "1h 多头", strategy_input.one_hour, "UP", effective_config, strategy_input.one_hour_regime))
        if four_hour_short and one_hour_short:
            candidates.append(SHORT_4H_HEDGE)
            diagnostics.extend(_trend_diagnostics(SHORT_4H_HEDGE, "日线多头", strategy_input.daily, "UP", effective_config, strategy_input.daily_regime))
            diagnostics.extend(_trend_diagnostics(SHORT_4H_HEDGE, "4h 空头", strategy_input.four_hour, "DOWN", effective_config, strategy_input.four_hour_regime))
            diagnostics.extend(_trend_diagnostics(SHORT_4H_HEDGE, "1h 空头", strategy_input.one_hour, "DOWN", effective_config, strategy_input.one_hour_regime))
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
        if _bearish_basis(strategy_input.daily):
            candidates.append(SHORT_DAY_CORE)
            diagnostics.extend(_core_strategy_diagnostics(SHORT_DAY_CORE, strategy_input, "DOWN", effective_config))
        elif _bullish_basis(strategy_input.daily):
            candidates.append(LONG_DAY_CORE)
            diagnostics.extend(_core_strategy_diagnostics(LONG_DAY_CORE, strategy_input, "UP", effective_config))
        else:
            diagnostics.extend(
                [
                    *_trend_diagnostics(SHORT_DAY_CORE, "日线空头", strategy_input.daily, "DOWN", effective_config, strategy_input.daily_regime),
                    *_trend_diagnostics(LONG_DAY_CORE, "日线多头", strategy_input.daily, "UP", effective_config, strategy_input.daily_regime),
                ]
            )

    return LayeredStrategyDecision(
        symbol=strategy_input.symbol,
        signal=signal,
        candidates=tuple(candidates),
        diagnostics=tuple(diagnostics),
    )


def _bullish(snapshot: TrendSnapshot, config: LayeredStrategyConfig) -> bool:
    return (
        _bullish_basis(snapshot)
        and _bullish_slope(snapshot)
        and _bullish_momentum(snapshot, config)
    )


def _regime_direction(regime: TrendRegime | None) -> str:
    if regime is None:
        return "UNKNOWN"
    direction = regime.direction.upper()
    return direction if direction in {"LONG", "SHORT"} else "UNKNOWN"


def _bearish(snapshot: TrendSnapshot, config: LayeredStrategyConfig) -> bool:
    return (
        _bearish_basis(snapshot)
        and _bearish_slope(snapshot)
        and _bearish_momentum(snapshot, config)
    )


def _bullish_basis(snapshot: TrendSnapshot) -> bool:
    return snapshot.fast_ma > snapshot.slow_ma


def _bearish_basis(snapshot: TrendSnapshot) -> bool:
    return snapshot.fast_ma < snapshot.slow_ma


def _bullish_slope(snapshot: TrendSnapshot) -> bool:
    return snapshot.fast_ma_slope > 0


def _bearish_slope(snapshot: TrendSnapshot) -> bool:
    return snapshot.fast_ma_slope < 0


def _bullish_momentum(snapshot: TrendSnapshot, config: LayeredStrategyConfig) -> bool:
    return snapshot.adx >= config.min_adx and snapshot.di_plus > snapshot.di_minus


def _bearish_momentum(snapshot: TrendSnapshot, config: LayeredStrategyConfig) -> bool:
    return snapshot.adx >= config.min_adx and snapshot.di_minus > snapshot.di_plus


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


def _core_strategy_diagnostics(
    strategy_type: str,
    strategy_input: LayeredStrategyInput,
    direction: str,
    config: LayeredStrategyConfig,
) -> list[dict[str, object]]:
    if direction == "UP":
        return [
            *_trend_diagnostics(strategy_type, "日线多头", strategy_input.daily, "UP", config, strategy_input.daily_regime),
            *_trend_diagnostics(strategy_type, "4h 多头", strategy_input.four_hour, "UP", config, strategy_input.four_hour_regime),
            *_trend_diagnostics(strategy_type, "1h 多头", strategy_input.one_hour, "UP", config, strategy_input.one_hour_regime),
            *_entry_diagnostics(strategy_type, "15m 多头", strategy_input.entry, "UP"),
        ]
    return [
        *_trend_diagnostics(strategy_type, "日线空头", strategy_input.daily, "DOWN", config, strategy_input.daily_regime),
        *_trend_diagnostics(strategy_type, "4h 空头", strategy_input.four_hour, "DOWN", config, strategy_input.four_hour_regime),
        *_trend_diagnostics(strategy_type, "1h 空头", strategy_input.one_hour, "DOWN", config, strategy_input.one_hour_regime),
        *_entry_diagnostics(strategy_type, "15m 空头", strategy_input.entry, "DOWN"),
    ]


def _trend_diagnostics(
    strategy_type: str,
    label: str,
    snapshot: TrendSnapshot,
    direction: str,
    config: LayeredStrategyConfig,
    regime: TrendRegime | None = None,
) -> list[dict[str, object]]:
    if direction == "UP":
        conditions = [
            _condition(strategy_type, f"{label}基础", _bullish_basis(snapshot), _ma_detail(snapshot, "UP")),
            *_regime_confirmation_condition(strategy_type, label, regime, "LONG"),
            _condition(strategy_type, f"{label}斜率", _bullish_slope(snapshot), _slope_detail(snapshot, "UP")),
        ]
        if regime is None:
            conditions.append(
                _condition(
                    strategy_type,
                    f"{label}动能",
                    _bullish_momentum(snapshot, config),
                    _momentum_detail(snapshot, config, "UP"),
                )
            )
        return conditions
    conditions = [
        _condition(strategy_type, f"{label}基础", _bearish_basis(snapshot), _ma_detail(snapshot, "DOWN")),
        *_regime_confirmation_condition(strategy_type, label, regime, "SHORT"),
        _condition(strategy_type, f"{label}斜率", _bearish_slope(snapshot), _slope_detail(snapshot, "DOWN")),
    ]
    if regime is None:
        conditions.append(
            _condition(
                strategy_type,
                f"{label}动能",
                _bearish_momentum(snapshot, config),
                _momentum_detail(snapshot, config, "DOWN"),
            )
        )
    return conditions


def _entry_diagnostics(
    strategy_type: str,
    label: str,
    entry: LayeredEntryFrame,
    direction: str,
) -> list[dict[str, object]]:
    if direction == "UP":
        return [
            _condition(strategy_type, f"{label}入场条件", _long_entry_setup(entry), _entry_setup_detail(entry, "UP")),
            _condition(strategy_type, f"{label}已确认", _bullish_entry_confirmation(entry), _entry_confirmation_detail(entry, "UP")),
            _condition(strategy_type, "止损有效", entry.close > entry.recent_swing_low, f"entry={entry.close} > swing_low={entry.recent_swing_low}"),
        ]
    return [
        _condition(strategy_type, f"{label}入场条件", _short_entry_setup(entry), _entry_setup_detail(entry, "DOWN")),
        _condition(strategy_type, f"{label}已确认", _bearish_entry_confirmation(entry), _entry_confirmation_detail(entry, "DOWN")),
        _condition(strategy_type, "止损有效", entry.close < entry.recent_swing_high, f"entry={entry.close} < swing_high={entry.recent_swing_high}"),
    ]


def _regime_confirmation_condition(
    strategy_type: str,
    label: str,
    regime: TrendRegime | None,
    expected_direction: str,
) -> list[dict[str, object]]:
    if regime is None:
        return []
    passed = _regime_direction(regime) == expected_direction
    detail = (
        f"confirmed_at_ms={regime.confirmed_at_ms}"
        if regime.confirmed_at_ms is not None
        else "confirmed_at_ms=-"
    )
    return [_condition(strategy_type, f"{label}已确认", passed, detail)]


def _condition(
    strategy_type: str,
    text: str,
    passed: bool,
    detail: str,
    required: bool = True,
) -> dict[str, object]:
    return {
        "strategy": strategy_type,
        "strategy_type": strategy_type,
        "text": text,
        "passed": passed,
        "detail": detail,
        "required": required,
    }


def _bullish_entry(entry: LayeredEntryFrame) -> bool:
    return _long_entry_setup(entry) and _bullish_entry_confirmation(entry) and entry.close > entry.recent_swing_low


def _bearish_entry(entry: LayeredEntryFrame) -> bool:
    return _short_entry_setup(entry) and _bearish_entry_confirmation(entry) and entry.close < entry.recent_swing_high


def _long_entry_setup(entry: LayeredEntryFrame) -> bool:
    return _long_entry_zone(entry) or entry.close > entry.fast_ma


def _short_entry_setup(entry: LayeredEntryFrame) -> bool:
    return _short_entry_zone(entry) or entry.close < entry.fast_ma


def _long_entry_zone(entry: LayeredEntryFrame) -> bool:
    zone = entry.atr
    return entry.low <= entry.fast_ma + zone and entry.close >= entry.fast_ma - zone


def _short_entry_zone(entry: LayeredEntryFrame) -> bool:
    zone = entry.atr
    return entry.high >= entry.fast_ma - zone and entry.close <= entry.fast_ma + zone


def _bullish_entry_confirmation(entry: LayeredEntryFrame) -> bool:
    return entry.close > entry.open


def _bearish_entry_confirmation(entry: LayeredEntryFrame) -> bool:
    return entry.close < entry.open


def _entry_setup_detail(entry: LayeredEntryFrame, direction: str) -> str:
    if direction == "UP":
        return (
            f"回踩区: low={entry.low} <= fast_ma+ATR={entry.fast_ma + entry.atr}, "
            f"close={entry.close} >= fast_ma-ATR={entry.fast_ma - entry.atr}; "
            f"顺势延续: close={entry.close} > fast_ma={entry.fast_ma}"
        )
    return (
        f"反弹区: high={entry.high} >= fast_ma-ATR={entry.fast_ma - entry.atr}, "
        f"close={entry.close} <= fast_ma+ATR={entry.fast_ma + entry.atr}; "
        f"顺势延续: close={entry.close} < fast_ma={entry.fast_ma}"
    )


def _entry_confirmation_detail(entry: LayeredEntryFrame, direction: str) -> str:
    if direction == "UP":
        return f"close={entry.close} > open={entry.open}"
    return f"close={entry.close} < open={entry.open}"


def _ma_detail(snapshot: TrendSnapshot, direction: str) -> str:
    if direction == "UP":
        return f"fast_ma={snapshot.fast_ma} > slow_ma={snapshot.slow_ma}"
    return f"fast_ma={snapshot.fast_ma} < slow_ma={snapshot.slow_ma}"


def _slope_detail(snapshot: TrendSnapshot, direction: str) -> str:
    if direction == "UP":
        return f"slope={snapshot.fast_ma_slope} > 0"
    return f"slope={snapshot.fast_ma_slope} < 0"


def _momentum_detail(
    snapshot: TrendSnapshot,
    config: LayeredStrategyConfig,
    direction: str,
) -> str:
    if direction == "UP":
        return (
            f"ADX={snapshot.adx} >= {config.min_adx}, "
            f"DI+={snapshot.di_plus} > DI-={snapshot.di_minus}"
        )
    return (
        f"ADX={snapshot.adx} >= {config.min_adx}, "
        f"DI-={snapshot.di_minus} > DI+={snapshot.di_plus}"
    )
