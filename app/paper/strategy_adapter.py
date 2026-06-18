from dataclasses import dataclass
from decimal import Decimal

from app.data.quality import Kline
from app.indicators.core import atr, directional_movement_index, ema
from app.paper.multitimeframe import MultiTimeframeFrame
from app.strategy.pullback_strategy import EntryFrame, TradeSignal, build_pullback_signal
from app.strategy.reversal_strategy import ReversalSetup, build_reversal_signal
from app.strategy.signal_router import SignalInputs, StrategySignal, select_signal
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
    )
    reversal_signal = build_reversal_signal(trend=trend, setup=reversal_setup)
    signal = select_signal(SignalInputs(main_signal=main_signal, reversal_signal=reversal_signal))
    return _attach_realtime_diagnostics(signal=signal, frame=frame, config=strategy_config)


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
    condition_statuses = _condition_statuses(frame=frame, config=config)
    return StrategySignal(
        action=signal.action,
        strategy_type=signal.strategy_type,
        reason=signal.reason,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        risk_reward=signal.risk_reward,
        signal_level=signal.signal_level,
        score=signal.score,
        risk_pct=signal.risk_pct,
        max_standard_position_pct=signal.max_standard_position_pct,
        core_rules=_core_rules(frame=frame, config=config),
        chart_points=_chart_points(frame.history(config.entry_interval), config=config),
        chart_timeframes=_chart_timeframes(frame=frame, config=config),
        condition_statuses=condition_statuses,
        nearest_strategy=_nearest_strategy(condition_statuses),
    )


def _core_rules(frame: MultiTimeframeFrame, config: RealtimeStrategyConfig) -> list[str]:
    rules: list[str] = []
    for interval in (*config.trend_intervals, config.entry_interval):
        klines = frame.history(interval)
        closes = [kline.close for kline in klines]
        if not closes:
            continue
        fast = ema(closes, config.ema_fast_period)[-1]
        slow = ema(closes, config.ema_slow_period)[-1]
        if fast is None or slow is None:
            continue
        if fast > slow:
            rules.append(f"{interval} EMA50 > EMA200：多头基础")
        elif slow > fast:
            rules.append(f"{interval} EMA200 > EMA50：空头基础")
        else:
            rules.append(f"{interval} EMA50 = EMA200：方向不明")
    rules.append("主策略：4h/1h 同向趋势 + 15m 回踩/反弹 EMA50 区域 + 确认 K 线")
    rules.append("趋势转换：4h/1h 冲突时评估 REVERSAL_PROBE 试仓")
    return rules


def _chart_points(
    klines: tuple[Kline, ...],
    config: RealtimeStrategyConfig,
    max_points: int = 80,
) -> list[dict[str, str]]:
    if not klines:
        return []
    closes = [kline.close for kline in klines]
    ema50_values = ema(closes, config.ema_fast_period)
    ema200_values = ema(closes, config.ema_slow_period)
    start = max(0, len(klines) - max_points)
    points: list[dict[str, str]] = []
    for kline, ema50_value, ema200_value in zip(
        klines[start:],
        ema50_values[start:],
        ema200_values[start:],
        strict=True,
    ):
        point = {
            "open_time": str(kline.open_time),
            "open": str(kline.open),
            "high": str(kline.high),
            "low": str(kline.low),
            "close": str(kline.close),
        }
        if ema50_value is not None:
            point["ema50"] = str(ema50_value)
        if ema200_value is not None:
            point["ema200"] = str(ema200_value)
        points.append(point)
    return points


def _chart_timeframes(
    frame: MultiTimeframeFrame,
    config: RealtimeStrategyConfig,
) -> dict[str, list[dict[str, str]]]:
    return {
        interval: _chart_points(frame.history(interval), config=config)
        for interval in (*config.trend_intervals, config.entry_interval)
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
        _condition("主趋势做多", "4h 上涨趋势", _trend_up(four_hour, config), _trend_detail(four_hour, "UP")),
        _condition("主趋势做多", "1h 上涨趋势", _trend_up(one_hour, config), _trend_detail(one_hour, "UP")),
        _condition(
            "主趋势做多",
            "15m 回踩到 EMA50 区域",
            _near_ema50(entry_frame),
            f"|close-EMA50|={_fmt_decimal(abs(entry_frame.close - entry_frame.ema50))} <= ATR={_fmt_decimal(entry_frame.atr)}",
        ),
        _condition(
            "主趋势做多",
            "15m 看涨确认",
            entry_frame.close > entry_frame.previous_close,
            f"close={_fmt_decimal(entry_frame.close)} > previous_close={_fmt_decimal(entry_frame.previous_close)}",
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
        _condition("主趋势做空", "4h 下跌趋势", _trend_down(four_hour, config), _trend_detail(four_hour, "DOWN")),
        _condition("主趋势做空", "1h 下跌趋势", _trend_down(one_hour, config), _trend_detail(one_hour, "DOWN")),
        _condition(
            "主趋势做空",
            "15m 反弹到 EMA50 区域",
            _near_ema50(entry_frame),
            f"|close-EMA50|={_fmt_decimal(abs(entry_frame.close - entry_frame.ema50))} <= ATR={_fmt_decimal(entry_frame.atr)}",
        ),
        _condition(
            "主趋势做空",
            "15m 看跌确认",
            entry_frame.close < entry_frame.previous_close,
            f"close={_fmt_decimal(entry_frame.close)} < previous_close={_fmt_decimal(entry_frame.previous_close)}",
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


def _near_ema50(frame: EntryFrame) -> bool:
    return abs(frame.close - frame.ema50) <= frame.atr


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
