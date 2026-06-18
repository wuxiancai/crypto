from dataclasses import dataclass, field
from decimal import Decimal

from app.data.quality import Kline


@dataclass(frozen=True)
class PaperConfig:
    initial_equity: Decimal
    risk_per_trade_pct: Decimal
    maker_fee_rate: Decimal
    taker_fee_rate: Decimal
    slippage_pct: Decimal
    default_stop_distance_pct: Decimal = Decimal("0.02")
    default_take_profit_risk_reward: Decimal = Decimal("2")


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


@dataclass(frozen=True)
class PaperSignalEvaluation:
    evaluated_at_ms: int
    symbol: str
    interval: str
    close: Decimal
    action: str
    strategy_type: str
    reason: tuple[str, ...]


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
        quantity = self._equity * risk_pct / stop_distance
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
        )

    def _maybe_close_position(self, position: PaperPosition, kline: Kline) -> PaperFill | None:
        if position.side == "LONG":
            if kline.low <= position.stop_loss:
                return self._close_position(position, kline, position.stop_loss, "STOP_LOSS")
            if kline.high >= position.take_profit:
                return self._close_position(position, kline, position.take_profit, "TAKE_PROFIT")
            return None
        if kline.high >= position.stop_loss:
            return self._close_position(position, kline, position.stop_loss, "STOP_LOSS")
        if kline.low <= position.take_profit:
            return self._close_position(position, kline, position.take_profit, "TAKE_PROFIT")
        return None

    def _close_position(
        self,
        position: PaperPosition,
        kline: Kline,
        raw_exit_price: Decimal,
        exit_reason: str,
    ) -> PaperFill:
        exit_price = _apply_exit_slippage(raw_exit_price, position.side, self._config.slippage_pct)
        if position.side == "LONG":
            gross_pnl = (exit_price - position.entry_price) * position.quantity
        else:
            gross_pnl = (position.entry_price - exit_price) * position.quantity
        exit_fee_rate = self._config.maker_fee_rate if exit_reason == "TAKE_PROFIT" else self._config.taker_fee_rate
        fees = position.entry_fee + exit_price * position.quantity * exit_fee_rate
        net_pnl = gross_pnl - fees
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
            net_pnl=net_pnl,
            exit_reason=exit_reason,
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
