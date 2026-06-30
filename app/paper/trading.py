from dataclasses import dataclass, field, replace
from decimal import Decimal

from app.data.quality import Kline
from app.execution.kill_switch import KillSwitchState
from app.execution.liquidation_guard import evaluate_liquidation_guard
from app.execution.stop_order_guard import (
    PositionSnapshot,
    StopOrderSnapshot,
    evaluate_stop_order_guard,
)


@dataclass(frozen=True)
class PaperConfig:
    initial_equity: Decimal
    risk_per_trade_pct: Decimal
    slippage_pct: Decimal
    maker_fee_rate: Decimal = Decimal("0.0002")
    taker_fee_rate: Decimal = Decimal("0.0005")
    leverage: Decimal = Decimal("10")
    funding_rate: Decimal = Decimal("0")
    funding_interval_ms: int = 8 * 60 * 60 * 1000
    default_stop_distance_pct: Decimal = Decimal("0.02")
    default_take_profit_risk_reward: Decimal = Decimal("2")
    trend_pullback_take_profit_mode: str = "TRAILING"
    trailing_atr_multiplier: Decimal = Decimal("2")
    trailing_atr_period: int = 14
    max_fee_to_risk_ratio: Decimal | None = Decimal("0.25")
    max_single_position_notional_leverage: Decimal | None = Decimal("5")
    max_total_planned_risk_pct: Decimal | None = Decimal("0.02")
    max_total_notional_leverage: Decimal | None = Decimal("10")
    liquidation_buffer_pct: Decimal = Decimal("0.01")
    max_drawdown_pct: Decimal | None = None
    kill_switch: KillSwitchState | None = None
    kill_switch_state: KillSwitchState | None = None


@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    side: str
    strategy_type: str
    entry_time: int
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    quantity: Decimal
    entry_fee: Decimal
    bucket: str = "LEGACY"
    leverage: Decimal = Decimal("10")
    initial_stop_loss: Decimal | None = None
    trailing_active: bool = False
    trailing_atr: Decimal | None = None
    trailing_last_close: Decimal | None = None
    interval: str = "15m"
    strategy_kernel: str | None = None
    position_level: str | None = None
    trade_mode: str | None = None
    market_regime: str | None = None
    lifecycle_state: str | None = None

    def __post_init__(self) -> None:
        if self.initial_stop_loss is None:
            object.__setattr__(self, "initial_stop_loss", self.stop_loss)


@dataclass(frozen=True)
class PaperFill:
    symbol: str
    side: str
    strategy_type: str
    entry_time: int
    exit_time: int
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    exit_reason: str
    bucket: str = "LEGACY"
    leverage: Decimal = Decimal("10")
    funding_fee: Decimal = Decimal("0")
    exit_detail: str = ""
    strategy_kernel: str | None = None
    position_level: str | None = None
    trade_mode: str | None = None
    market_regime: str | None = None
    lifecycle_state: str | None = None


@dataclass(frozen=True)
class PaperSignalEvaluation:
    evaluated_at_ms: int
    symbol: str
    interval: str
    close: Decimal
    action: str
    strategy_type: str
    reason: tuple[str, ...]
    core_rules: tuple[str, ...] = ()
    chart_points: tuple[dict[str, str], ...] = ()
    chart_timeframes: dict[str, tuple[dict[str, str], ...]] = field(default_factory=dict)
    condition_statuses: tuple[dict[str, object], ...] = ()
    nearest_strategy: dict[str, object] = field(default_factory=dict)
    strategy_kernel: str | None = None
    position_level: str | None = None
    trade_mode: str | None = None
    market_regime: str | None = None
    lifecycle_state: str | None = None


@dataclass(frozen=True)
class PaperSnapshot:
    equity: Decimal
    open_position: PaperPosition | None
    fills: list[PaperFill]
    rejected_signals: int
    open_positions: list[PaperPosition] = field(default_factory=list)
    runtime_started_at_ms: int | None = None
    last_update_at_ms: int | None = None
    signal_evaluations: list[PaperSignalEvaluation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.open_positions and self.open_position is not None:
            object.__setattr__(self, "open_positions", [self.open_position])


class SignalLike:
    action: str
    strategy_type: str
    entry_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    strategy_kernel: str | None
    position_level: str | None
    trade_mode: str | None
    reduce_pct: Decimal | None


class PaperTradingEngine:
    def __init__(self, config: PaperConfig) -> None:
        self._config = config
        self._equity = config.initial_equity
        self._positions: list[PaperPosition] = []
        self._fills: list[PaperFill] = []
        self._rejected_signals = 0

    @classmethod
    def from_snapshot(cls, config: PaperConfig, snapshot: PaperSnapshot) -> "PaperTradingEngine":
        engine = cls(config)
        engine._equity = snapshot.equity
        engine._positions = list(snapshot.open_positions or [])
        if not engine._positions and snapshot.open_position is not None:
            engine._positions = [snapshot.open_position]
        engine._fills = list(snapshot.fills)
        engine._rejected_signals = snapshot.rejected_signals
        return engine

    def on_signal(self, kline: Kline, signal: SignalLike) -> PaperPosition | PaperFill | None:
        if signal.action == "EXIT_POSITION":
            return self._exit_position_by_signal(kline, signal)
        if signal.action == "REDUCE_POSITION":
            return self._reduce_position_by_signal(kline, signal)
        if signal.action not in {"LONG_ENTRY", "SHORT_ENTRY", "REVERSAL_LONG_ENTRY", "REVERSAL_SHORT_ENTRY"}:
            return None
        if self._kill_switch_blocks_new_entries():
            self._rejected_signals += 1
            return None
        if self._has_conflicting_position(kline.symbol, signal):
            self._rejected_signals += 1
            return None
        position = self._open_position(kline, signal)
        if position is None:
            self._rejected_signals += 1
            return None
        self._positions.append(position)
        return position

    def on_kline_all(self, kline: Kline) -> list[PaperFill]:
        """Evaluate every coexisting sub-position against this kline.

        A single kline can close more than one position. Positions that are not
        closed are still updated in place by ``_maybe_close_position`` (trailing
        stop), so all open sub-positions are processed on every kline.
        """
        fills: list[PaperFill] = []
        for position in list(self._positions):
            if position.symbol != kline.symbol or position.interval != kline.interval:
                continue
            fill = self._kill_switch_fill(position, kline) or self._maybe_close_position(position, kline)
            if fill is None:
                continue
            self._fills.append(fill)
            self._equity += fill.net_pnl
            self._positions.remove(position)
            fills.append(fill)
        return fills

    def on_kline(self, kline: Kline) -> PaperFill | None:
        """Backward-compatible wrapper returning the first close (if any).

        Prefer :meth:`on_kline_all` in the runtime so coexisting sub-positions
        are not skipped.
        """
        fills = self.on_kline_all(kline)
        return fills[0] if fills else None

    def snapshot(self) -> PaperSnapshot:
        return PaperSnapshot(
            equity=self._equity,
            open_position=self._positions[0] if self._positions else None,
            open_positions=list(self._positions),
            fills=list(self._fills),
            rejected_signals=self._rejected_signals,
        )

    def _has_conflicting_position(self, symbol: str, signal: SignalLike) -> bool:
        signal_level = getattr(signal, "position_level", None)
        if signal_level:
            for position in self._positions:
                if position.symbol != symbol:
                    continue
                if position.strategy_kernel and position.strategy_kernel != getattr(signal, "strategy_kernel", None):
                    return True
                if position.position_level == signal_level:
                    return True
            return False
        bucket = _bucket_from_signal(signal)
        for position in self._positions:
            if position.symbol != symbol:
                continue
            if position.bucket == bucket:
                return True
            if bucket == "LEGACY" or position.bucket == "LEGACY":
                return True
        return False

    def _open_position(self, kline: Kline, signal: SignalLike) -> PaperPosition | None:
        side = _side_from_action(signal.action)
        raw_entry_price = getattr(signal, "entry_price", None) or kline.close
        stop_loss = getattr(signal, "stop_loss", None) or _default_stop_loss(raw_entry_price, side, self._config)
        take_profit = getattr(signal, "take_profit", None) or _default_take_profit(
            raw_entry_price,
            stop_loss,
            side,
            self._config,
        )
        entry_price = _apply_entry_slippage(raw_entry_price, side, self._config.slippage_pct)
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance <= 0:
            raise ValueError("stop distance must be positive")
        signal_risk_pct = getattr(signal, "risk_pct", None)
        risk_pct = signal_risk_pct if signal_risk_pct is not None else self._config.risk_per_trade_pct
        risk_multiplier = getattr(signal, "risk_multiplier", Decimal("1"))
        if risk_multiplier < 0:
            risk_multiplier = Decimal("0")
        risk_pct = risk_pct * risk_multiplier
        if risk_pct <= 0:
            return None
        risk_quantity = self._equity * risk_pct / stop_distance
        max_notional_quantity = self._max_single_position_quantity(entry_price)
        quantity = min(risk_quantity, max_notional_quantity)
        if quantity <= 0:
            return None
        entry_fee = entry_price * quantity * self._config.taker_fee_rate
        estimated_stop_fee = stop_loss * quantity * self._config.taker_fee_rate
        planned_risk = stop_distance * quantity
        planned_notional = entry_price * quantity
        if _fees_too_high_for_planned_risk(
            fees=entry_fee + estimated_stop_fee,
            planned_risk=planned_risk,
            max_ratio=self._config.max_fee_to_risk_ratio,
        ):
            return None
        if _bucket_from_signal(signal) != "LEGACY" and self._portfolio_risk_exceeded(planned_risk, planned_notional):
            return None
        position = PaperPosition(
            symbol=kline.symbol,
            side=side,
            strategy_type=signal.strategy_type,
            bucket=_bucket_from_signal(signal),
            entry_time=kline.open_time,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            quantity=quantity,
            entry_fee=entry_fee,
            leverage=self._config.leverage,
            initial_stop_loss=stop_loss,
            interval=kline.interval,
            trailing_atr=getattr(signal, "trailing_atr", None) or getattr(signal, "atr", None),
            trailing_last_close=entry_price,
            strategy_kernel=getattr(signal, "strategy_kernel", None),
            position_level=getattr(signal, "position_level", None),
            trade_mode=getattr(signal, "trade_mode", None),
            market_regime=getattr(signal, "market_regime", None),
            lifecycle_state=getattr(signal, "lifecycle_state", "OPEN") or "OPEN",
        )
        if not self._liquidation_guard_allows(position):
            return None
        if not self._stop_order_guard_allows(position):
            return None
        return position

    def _exit_position_by_signal(self, kline: Kline, signal: SignalLike) -> PaperFill | None:
        target = self._find_position_for_signal(kline.symbol, signal)
        if target is None:
            return None
        fill = self._close_position(
            position=target,
            kline=kline,
            raw_exit_price=kline.close,
            exit_reason="KERNEL_FORCED_EXIT",
            exit_detail="新版策略内核触发强制退出",
        )
        self._fills.append(fill)
        self._equity += fill.net_pnl
        self._positions.remove(target)
        return fill

    def _reduce_position_by_signal(self, kline: Kline, signal: SignalLike) -> PaperFill | None:
        target = self._find_position_for_signal(kline.symbol, signal)
        if target is None:
            return None
        reduce_pct = getattr(signal, "reduce_pct", None) or Decimal("0.5")
        reduce_pct = max(Decimal("0"), min(Decimal("1"), reduce_pct))
        if reduce_pct <= 0:
            return None
        if reduce_pct >= 1:
            return self._exit_position_by_signal(kline, signal)
        reduced_quantity = target.quantity * reduce_pct
        remaining = replace(
            target,
            quantity=target.quantity - reduced_quantity,
            entry_fee=target.entry_fee * (Decimal("1") - reduce_pct),
            lifecycle_state="REDUCING",
        )
        partial = replace(
            target,
            quantity=reduced_quantity,
            entry_fee=target.entry_fee * reduce_pct,
            lifecycle_state="REDUCING",
        )
        fill = self._close_position(
            position=partial,
            kline=kline,
            raw_exit_price=kline.close,
            exit_reason="KERNEL_STAGED_REDUCTION",
            exit_detail=f"新版策略内核触发分批减仓 {reduce_pct}",
        )
        self._replace_position(target, remaining)
        self._fills.append(fill)
        self._equity += fill.net_pnl
        return fill

    def _find_position_for_signal(self, symbol: str, signal: SignalLike) -> PaperPosition | None:
        signal_level = getattr(signal, "position_level", None)
        signal_kernel = getattr(signal, "strategy_kernel", None)
        for position in self._positions:
            if position.symbol != symbol:
                continue
            if signal_kernel and position.strategy_kernel != signal_kernel:
                continue
            if signal_level and position.position_level != signal_level:
                continue
            return position
        return None

    def _kill_switch_blocks_new_entries(self) -> bool:
        state = self._kill_switch_state()
        return bool(state is not None and state.is_active and not state.allow_new_entries) or self._max_drawdown_reached()

    def _kill_switch_state(self) -> KillSwitchState | None:
        return self._config.kill_switch_state or self._config.kill_switch

    def _max_drawdown_reached(self) -> bool:
        max_drawdown_pct = self._config.max_drawdown_pct
        if max_drawdown_pct is None or max_drawdown_pct <= 0:
            return False
        floor_equity = self._config.initial_equity * (Decimal("1") - max_drawdown_pct)
        return self._equity <= floor_equity

    def _kill_switch_fill(self, position: PaperPosition, kline: Kline) -> PaperFill | None:
        state = self._kill_switch_state()
        if state is None or not state.is_active or not state.close_positions:
            return None
        return self._close_position(
            position=position,
            kline=kline,
            raw_exit_price=kline.close,
            exit_reason="KILL_SWITCH",
            exit_detail=f"Kill switch active: {state.reason}",
        )

    def _liquidation_guard_allows(self, position: PaperPosition) -> bool:
        result = evaluate_liquidation_guard(
            side=position.side,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            estimated_liquidation_price=_estimated_liquidation_price(position),
            liquidation_buffer_pct=self._config.liquidation_buffer_pct,
        )
        return result.is_safe

    def _stop_order_guard_allows(self, position: PaperPosition) -> bool:
        result = evaluate_stop_order_guard(
            PositionSnapshot(
                symbol=position.symbol,
                side=position.side,
                quantity=position.quantity,
                entry_price=position.entry_price,
            ),
            [
                StopOrderSnapshot(
                    symbol=position.symbol,
                    side="SELL" if position.side == "LONG" else "BUY",
                    quantity=position.quantity,
                    stop_price=position.stop_loss,
                    reduce_only=True,
                    status="NEW",
                )
            ],
        )
        return result.is_protected

    def _max_single_position_quantity(self, entry_price: Decimal) -> Decimal:
        max_notional = self._equity * self._config.leverage
        max_single_leverage = self._config.max_single_position_notional_leverage
        if max_single_leverage is not None and max_single_leverage > 0:
            max_notional = min(max_notional, self._equity * max_single_leverage)
        return max_notional / entry_price

    def _portfolio_risk_exceeded(self, planned_risk: Decimal, planned_notional: Decimal) -> bool:
        max_risk_pct = self._config.max_total_planned_risk_pct
        if max_risk_pct is not None and max_risk_pct > 0:
            max_risk = self._equity * max_risk_pct
            if _open_planned_risk(self._positions) + planned_risk > max_risk:
                return True
        max_notional_leverage = self._config.max_total_notional_leverage
        if max_notional_leverage is not None and max_notional_leverage > 0:
            max_notional = self._equity * max_notional_leverage
            if _open_notional(self._positions) + planned_notional > max_notional:
                return True
        return False

    def _maybe_close_position(self, position: PaperPosition, kline: Kline) -> PaperFill | None:
        liquidation_fill = self._liquidation_fill(position, kline)
        if liquidation_fill is not None:
            return liquidation_fill
        if position.side == "LONG":
            if kline.low <= position.stop_loss:
                # Gap-aware fill: if the bar opens below the stop, fill at the
                # (worse) open price rather than optimistically at the stop.
                # Mirrors app/backtest/engine.py so paper and backtest agree.
                raw_exit_price = min(kline.open, position.stop_loss)
                return self._close_position(
                    position,
                    kline,
                    raw_exit_price,
                    _stop_exit_reason(position),
                    _stop_exit_detail(position, "最低价"),
                )
            if kline.high >= position.take_profit:
                return self._handle_take_profit(position, kline)
            self._replace_position(position, _trail_position(position, kline, self._config))
            return None
        if kline.high >= position.stop_loss:
            raw_exit_price = max(kline.open, position.stop_loss)
            return self._close_position(
                position,
                kline,
                raw_exit_price,
                _stop_exit_reason(position),
                _stop_exit_detail(position, "最高价"),
            )
        if kline.low <= position.take_profit:
            return self._handle_take_profit(position, kline)
        self._replace_position(position, _trail_position(position, kline, self._config))
        return None

    def _liquidation_fill(self, position: PaperPosition, kline: Kline) -> PaperFill | None:
        liquidation_price = _estimated_liquidation_price(position)
        if position.side == "LONG" and kline.low <= liquidation_price:
            return self._close_position(
                position,
                kline,
                liquidation_price,
                "LIQUIDATION",
                "强平风险：最低价触达估算强平价",
            )
        if position.side == "SHORT" and kline.high >= liquidation_price:
            return self._close_position(
                position,
                kline,
                liquidation_price,
                "LIQUIDATION",
                "强平风险：最高价触达估算强平价",
            )
        return None

    def _handle_take_profit(self, position: PaperPosition, kline: Kline) -> PaperFill | None:
        if _uses_trailing_take_profit(position, self._config):
            self._replace_position(position, _activate_trailing_take_profit(position, kline, self._config))
            return None
        return self._close_position(
            position,
            kline,
            position.take_profit,
            "TAKE_PROFIT",
            _take_profit_detail(position),
        )

    def _close_position(
        self,
        position: PaperPosition,
        kline: Kline,
        raw_exit_price: Decimal,
        exit_reason: str,
        exit_detail: str,
    ) -> PaperFill:
        exit_price = _apply_exit_slippage(raw_exit_price, position.side, self._config.slippage_pct)
        if position.side == "LONG":
            gross_pnl = (exit_price - position.entry_price) * position.quantity
        else:
            gross_pnl = (position.entry_price - exit_price) * position.quantity
        exit_fee_rate = self._config.maker_fee_rate if exit_reason == "TAKE_PROFIT" else self._config.taker_fee_rate
        fees = position.entry_fee + exit_price * position.quantity * exit_fee_rate
        funding_fee = _funding_fee(position, kline.close_time, self._config)
        net_pnl = gross_pnl - fees - funding_fee
        return PaperFill(
            symbol=position.symbol,
            side=position.side,
            strategy_type=position.strategy_type,
            bucket=position.bucket,
            entry_time=position.entry_time,
            exit_time=kline.close_time,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            leverage=position.leverage,
            gross_pnl=gross_pnl,
            fees=fees,
            funding_fee=funding_fee,
            net_pnl=net_pnl,
            exit_reason=exit_reason,
            exit_detail=exit_detail,
            strategy_kernel=position.strategy_kernel,
            position_level=position.position_level,
            trade_mode=position.trade_mode,
            market_regime=position.market_regime,
            lifecycle_state=position.lifecycle_state,
        )

    def _replace_position(self, old: PaperPosition, new: PaperPosition) -> None:
        for index, position in enumerate(self._positions):
            if position is old:
                self._positions[index] = new
                return
        for index, position in enumerate(self._positions):
            if (
                position.symbol == old.symbol
                and position.bucket == old.bucket
                and position.entry_time == old.entry_time
            ):
                self._positions[index] = new
                return


def _side_from_action(action: str) -> str:
    if action in {"LONG_ENTRY", "REVERSAL_LONG_ENTRY"}:
        return "LONG"
    if action in {"SHORT_ENTRY", "REVERSAL_SHORT_ENTRY"}:
        return "SHORT"
    raise ValueError(f"unsupported paper entry action: {action}")


def _apply_entry_slippage(price: Decimal, side: str, slippage_pct: Decimal) -> Decimal:
    if side == "LONG":
        return price * (Decimal("1") + slippage_pct)
    return price * (Decimal("1") - slippage_pct)


def _apply_exit_slippage(price: Decimal, side: str, slippage_pct: Decimal) -> Decimal:
    if side == "LONG":
        return price * (Decimal("1") - slippage_pct)
    return price * (Decimal("1") + slippage_pct)


def _default_stop_loss(entry_price: Decimal, side: str, config: PaperConfig) -> Decimal:
    if side == "LONG":
        return entry_price * (Decimal("1") - config.default_stop_distance_pct)
    return entry_price * (Decimal("1") + config.default_stop_distance_pct)


def _default_take_profit(entry_price: Decimal, stop_loss: Decimal, side: str, config: PaperConfig) -> Decimal:
    risk = abs(entry_price - stop_loss)
    if side == "LONG":
        return entry_price + risk * config.default_take_profit_risk_reward
    return entry_price - risk * config.default_take_profit_risk_reward


def _funding_fee(position: PaperPosition, exit_time: int, config: PaperConfig) -> Decimal:
    if config.funding_rate == 0 or config.funding_interval_ms <= 0:
        return Decimal("0")
    settlements = _funding_settlement_count(position.entry_time, exit_time, config.funding_interval_ms)
    if settlements <= 0:
        return Decimal("0")
    signed_fee = position.entry_price * position.quantity * config.funding_rate * Decimal(settlements)
    return signed_fee if position.side == "LONG" else -signed_fee


def _funding_settlement_count(entry_time: int, exit_time: int, interval_ms: int) -> int:
    first = entry_time // interval_ms + 1
    last = exit_time // interval_ms
    return max(0, last - first + 1)


def _estimated_liquidation_price(position: PaperPosition) -> Decimal:
    if position.leverage <= 0:
        return position.entry_price
    liquidation_distance = position.entry_price / position.leverage
    if position.side == "LONG":
        return position.entry_price - liquidation_distance
    return position.entry_price + liquidation_distance


def _open_planned_risk(positions: list[PaperPosition]) -> Decimal:
    return sum((_position_planned_risk(position) for position in positions), Decimal("0"))


def _position_planned_risk(position: PaperPosition) -> Decimal:
    initial_stop = position.initial_stop_loss or position.stop_loss
    return abs(position.entry_price - initial_stop) * position.quantity


def _open_notional(positions: list[PaperPosition]) -> Decimal:
    return sum((position.entry_price * position.quantity for position in positions), Decimal("0"))


def _fees_too_high_for_planned_risk(
    fees: Decimal,
    planned_risk: Decimal,
    max_ratio: Decimal | None,
) -> bool:
    if max_ratio is None or max_ratio <= 0 or planned_risk <= 0:
        return False
    return fees / planned_risk > max_ratio


def _bucket_from_signal(signal: SignalLike) -> str:
    position_level = getattr(signal, "position_level", None)
    if position_level:
        return str(position_level)
    explicit_bucket = getattr(signal, "bucket", None)
    if explicit_bucket:
        return str(explicit_bucket)
    return "LEGACY"


def _uses_trailing_take_profit(position: PaperPosition, config: PaperConfig) -> bool:
    if config.trend_pullback_take_profit_mode != "TRAILING":
        return False
    if position.strategy_kernel == "WEEKLY_DAILY_H4_V1":
        return True
    return False


def _activate_trailing_take_profit(position: PaperPosition, kline: Kline, config: PaperConfig) -> PaperPosition:
    activated = replace(position, trailing_active=True)
    return _trail_position(activated, kline, config)


def _trail_position(position: PaperPosition, kline: Kline, config: PaperConfig) -> PaperPosition:
    refreshed = _refresh_trailing_atr(position, kline, config)
    if not refreshed.trailing_active:
        return refreshed
    if refreshed.side == "LONG":
        candidate_stop = _long_atr_take_profit(refreshed, kline.high, config)
        new_stop = max(refreshed.stop_loss, candidate_stop)
    else:
        candidate_stop = _short_atr_take_profit(refreshed, kline.low, config)
        new_stop = min(refreshed.stop_loss, candidate_stop)
    return replace(refreshed, stop_loss=new_stop)


def _initial_risk_per_unit(position: PaperPosition) -> Decimal:
    initial_stop = position.initial_stop_loss or position.stop_loss
    return abs(position.entry_price - initial_stop)


def _refresh_trailing_atr(position: PaperPosition, kline: Kline, config: PaperConfig) -> PaperPosition:
    if position.trailing_atr is None or position.trailing_atr <= 0:
        return position
    period = max(1, config.trailing_atr_period)
    previous_close = position.trailing_last_close or position.entry_price
    true_range = _true_range(kline, previous_close)
    updated_atr = ((position.trailing_atr * Decimal(period - 1)) + true_range) / Decimal(period)
    return replace(position, trailing_atr=updated_atr, trailing_last_close=kline.close)


def _true_range(kline: Kline, previous_close: Decimal) -> Decimal:
    return max(
        kline.high - kline.low,
        abs(kline.high - previous_close),
        abs(kline.low - previous_close),
    )


def _long_atr_take_profit(position: PaperPosition, high: Decimal, config: PaperConfig) -> Decimal:
    if position.trailing_atr is None or position.trailing_atr <= 0 or config.trailing_atr_multiplier <= 0:
        return _long_step_take_profit(position, high)
    atr_stop = high - position.trailing_atr * config.trailing_atr_multiplier
    min_protect = position.entry_price + _initial_risk_per_unit(position)
    return max(min_protect, atr_stop)


def _short_atr_take_profit(position: PaperPosition, low: Decimal, config: PaperConfig) -> Decimal:
    if position.trailing_atr is None or position.trailing_atr <= 0 or config.trailing_atr_multiplier <= 0:
        return _short_step_take_profit(position, low)
    atr_stop = low + position.trailing_atr * config.trailing_atr_multiplier
    min_protect = position.entry_price - _initial_risk_per_unit(position)
    return min(min_protect, atr_stop)


def _long_step_take_profit(position: PaperPosition, high: Decimal) -> Decimal:
    step_size = _initial_risk_per_unit(position) * Decimal("2")
    completed_steps = int((high - position.entry_price) // step_size)
    if completed_steps <= 0:
        return position.stop_loss

    candidate = position.entry_price + step_size * Decimal(max(0, completed_steps - 1))
    min_protect = position.entry_price + _initial_risk_per_unit(position)

    new_stop = candidate if candidate > min_protect else min_protect
    return new_stop


def _short_step_take_profit(position: PaperPosition, low: Decimal) -> Decimal:
    step_size = _initial_risk_per_unit(position) * Decimal("2")
    completed_steps = int((position.entry_price - low) // step_size)
    if completed_steps <= 0:
        return position.stop_loss

    candidate = position.entry_price - step_size * Decimal(max(0, completed_steps - 1))
    min_protect = position.entry_price - _initial_risk_per_unit(position)

    new_stop = candidate if candidate < min_protect else min_protect
    return new_stop


def _stop_exit_reason(position: PaperPosition) -> str:
    return "TRAILING_TAKE_PROFIT" if position.trailing_active else "STOP_LOSS"


def _stop_exit_detail(position: PaperPosition, trigger_price_label: str) -> str:
    if position.trailing_active:
        return f"{_side_action_label(position.side)}移动止盈：{trigger_price_label}触达移动止盈价 {position.stop_loss}"
    return f"{_side_action_label(position.side)}止损：{trigger_price_label}触达止损价 {position.stop_loss}"


def _take_profit_detail(position: PaperPosition) -> str:
    trigger_price_label = "最高价" if position.side == "LONG" else "最低价"
    return f"{_side_action_label(position.side)}止盈：{trigger_price_label}触达止盈价 {position.take_profit}"


def _side_action_label(side: str) -> str:
    return "做多" if side == "LONG" else "做空"
