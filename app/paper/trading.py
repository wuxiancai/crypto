from dataclasses import dataclass, field, replace
from decimal import Decimal

from app.data.quality import Kline


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
    initial_stop_loss: Decimal | None = None
    trailing_active: bool = False

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
    funding_fee: Decimal = Decimal("0")
    exit_detail: str = ""


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


@dataclass(frozen=True)
class PaperSnapshot:
    equity: Decimal
    open_position: PaperPosition | None
    fills: list[PaperFill]
    rejected_signals: int
    runtime_started_at_ms: int | None = None
    last_update_at_ms: int | None = None
    signal_evaluations: list[PaperSignalEvaluation] = field(default_factory=list)


class SignalLike:
    action: str
    strategy_type: str
    entry_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None


class PaperTradingEngine:
    def __init__(self, config: PaperConfig) -> None:
        self._config = config
        self._equity = config.initial_equity
        self._position: PaperPosition | None = None
        self._fills: list[PaperFill] = []
        self._rejected_signals = 0

    @classmethod
    def from_snapshot(cls, config: PaperConfig, snapshot: PaperSnapshot) -> "PaperTradingEngine":
        engine = cls(config)
        engine._equity = snapshot.equity
        engine._position = snapshot.open_position
        engine._fills = list(snapshot.fills)
        engine._rejected_signals = snapshot.rejected_signals
        return engine

    def on_signal(self, kline: Kline, signal: SignalLike) -> PaperPosition | None:
        if signal.action not in {"LONG_ENTRY", "SHORT_ENTRY", "REVERSAL_LONG_ENTRY", "REVERSAL_SHORT_ENTRY"}:
            return None
        if self._position is not None:
            self._rejected_signals += 1
            return None
        self._position = self._open_position(kline, signal)
        return self._position

    def on_kline(self, kline: Kline) -> PaperFill | None:
        if self._position is None:
            return None
        fill = self._maybe_close_position(self._position, kline)
        if fill is None:
            return None
        self._fills.append(fill)
        self._equity += fill.net_pnl
        self._position = None
        return fill

    def snapshot(self) -> PaperSnapshot:
        return PaperSnapshot(
            equity=self._equity,
            open_position=self._position,
            fills=list(self._fills),
            rejected_signals=self._rejected_signals,
        )

    def _open_position(self, kline: Kline, signal: SignalLike) -> PaperPosition:
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
        risk_pct = getattr(signal, "risk_pct", None) or self._config.risk_per_trade_pct
        risk_quantity = self._equity * risk_pct / stop_distance
        max_notional_quantity = self._equity * self._config.leverage / entry_price
        quantity = min(risk_quantity, max_notional_quantity)
        entry_fee = entry_price * quantity * self._config.taker_fee_rate
        return PaperPosition(
            symbol=kline.symbol,
            side=side,
            strategy_type=signal.strategy_type,
            entry_time=kline.open_time,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            quantity=quantity,
            entry_fee=entry_fee,
            initial_stop_loss=stop_loss,
        )

    def _maybe_close_position(self, position: PaperPosition, kline: Kline) -> PaperFill | None:
        if position.side == "LONG":
            if kline.low <= position.stop_loss:
                return self._close_position(
                    position,
                    kline,
                    position.stop_loss,
                    _stop_exit_reason(position),
                    _stop_exit_detail(position, "最低价"),
                )
            if kline.high >= position.take_profit:
                return self._handle_take_profit(position, kline)
            self._position = _trail_position(position, kline)
            return None
        if kline.high >= position.stop_loss:
            return self._close_position(
                position,
                kline,
                position.stop_loss,
                _stop_exit_reason(position),
                _stop_exit_detail(position, "最高价"),
            )
        if kline.low <= position.take_profit:
            return self._handle_take_profit(position, kline)
        self._position = _trail_position(position, kline)
        return None

    def _handle_take_profit(self, position: PaperPosition, kline: Kline) -> PaperFill | None:
        if _uses_trailing_take_profit(position, self._config):
            self._position = _activate_trailing_take_profit(position, kline)
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
            entry_time=position.entry_time,
            exit_time=kline.close_time,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            gross_pnl=gross_pnl,
            fees=fees,
            funding_fee=funding_fee,
            net_pnl=net_pnl,
            exit_reason=exit_reason,
            exit_detail=exit_detail,
        )


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


def _uses_trailing_take_profit(position: PaperPosition, config: PaperConfig) -> bool:
    return (
        position.strategy_type == "TREND_PULLBACK"
        and config.trend_pullback_take_profit_mode == "TRAILING"
    )


def _activate_trailing_take_profit(position: PaperPosition, kline: Kline) -> PaperPosition:
    activated = replace(position, trailing_active=True)
    return _trail_position(activated, kline)


def _trail_position(position: PaperPosition, kline: Kline) -> PaperPosition:
    if not position.trailing_active:
        return position
    if position.side == "LONG":
        step_stop = _long_step_take_profit(position, kline.high)
        new_stop = max(position.stop_loss, step_stop)
    else:
        step_stop = _short_step_take_profit(position, kline.low)
        new_stop = min(position.stop_loss, step_stop)
    return replace(position, stop_loss=new_stop)


def _initial_risk_per_unit(position: PaperPosition) -> Decimal:
    initial_stop = position.initial_stop_loss or position.stop_loss
    return abs(position.entry_price - initial_stop)


def _long_step_take_profit(position: PaperPosition, high: Decimal) -> Decimal:
    step_size = _initial_risk_per_unit(position) * Decimal("2")
    completed_steps = int((high - position.entry_price) // step_size)
    if completed_steps <= 0:
        return position.stop_loss
    return position.entry_price + step_size * Decimal(completed_steps)


def _short_step_take_profit(position: PaperPosition, low: Decimal) -> Decimal:
    step_size = _initial_risk_per_unit(position) * Decimal("2")
    completed_steps = int((position.entry_price - low) // step_size)
    if completed_steps <= 0:
        return position.stop_loss
    return position.entry_price - step_size * Decimal(completed_steps)


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
