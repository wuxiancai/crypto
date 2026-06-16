from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from app.data.quality import Kline


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: Decimal
    risk_per_trade_pct: Decimal
    fee_rate: Decimal
    slippage_pct: Decimal


@dataclass(frozen=True)
class BacktestTrade:
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
class BacktestResult:
    initial_equity: Decimal
    final_equity: Decimal
    trades: list[BacktestTrade]


@dataclass(frozen=True)
class _Position:
    symbol: str
    side: str
    strategy_type: str
    entry_time: int
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    quantity: Decimal
    entry_fee: Decimal


class SignalLike:
    action: str
    strategy_type: str
    entry_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None


SignalFn = Callable[[Kline, bool], SignalLike]


def run_backtest(klines: list[Kline], signal_fn: SignalFn, config: BacktestConfig) -> BacktestResult:
    equity = config.initial_equity
    trades: list[BacktestTrade] = []
    position: _Position | None = None

    for kline in sorted(klines, key=lambda row: row.open_time):
        if position is not None:
            trade = _maybe_close_position(position, kline, config)
            if trade is not None:
                trades.append(trade)
                equity += trade.net_pnl
                position = None
                continue

        signal = signal_fn(kline, position is not None)
        if position is None and signal.action in {"LONG_ENTRY", "SHORT_ENTRY"}:
            position = _open_position(kline, signal, equity, config)

    return BacktestResult(initial_equity=config.initial_equity, final_equity=equity, trades=trades)


def _open_position(kline: Kline, signal: SignalLike, equity: Decimal, config: BacktestConfig) -> _Position:
    if signal.entry_price is None or signal.stop_loss is None or signal.take_profit is None:
        raise ValueError("entry signal must include entry_price, stop_loss and take_profit")

    side = "LONG" if signal.action == "LONG_ENTRY" else "SHORT"
    entry_price = _apply_entry_slippage(signal.entry_price, side, config.slippage_pct)
    stop_distance = abs(entry_price - signal.stop_loss)
    if stop_distance <= 0:
        raise ValueError("stop distance must be positive")

    risk_amount = equity * config.risk_per_trade_pct
    quantity = risk_amount / stop_distance
    entry_fee = entry_price * quantity * config.fee_rate
    return _Position(
        symbol=kline.symbol,
        side=side,
        strategy_type=signal.strategy_type,
        entry_time=kline.open_time,
        entry_price=entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        quantity=quantity,
        entry_fee=entry_fee,
    )


def _maybe_close_position(position: _Position, kline: Kline, config: BacktestConfig) -> BacktestTrade | None:
    if position.side == "LONG":
        if kline.low <= position.stop_loss:
            return _close_position(position, kline, position.stop_loss, "STOP_LOSS", config)
        if kline.high >= position.take_profit:
            return _close_position(position, kline, position.take_profit, "TAKE_PROFIT", config)
        return None

    if kline.high >= position.stop_loss:
        return _close_position(position, kline, position.stop_loss, "STOP_LOSS", config)
    if kline.low <= position.take_profit:
        return _close_position(position, kline, position.take_profit, "TAKE_PROFIT", config)
    return None


def _close_position(
    position: _Position,
    kline: Kline,
    raw_exit_price: Decimal,
    exit_reason: str,
    config: BacktestConfig,
) -> BacktestTrade:
    exit_price = _apply_exit_slippage(raw_exit_price, position.side, config.slippage_pct)
    if position.side == "LONG":
        gross_pnl = (exit_price - position.entry_price) * position.quantity
    else:
        gross_pnl = (position.entry_price - exit_price) * position.quantity
    exit_fee = exit_price * position.quantity * config.fee_rate
    fees = position.entry_fee + exit_fee
    net_pnl = gross_pnl - fees
    return BacktestTrade(
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


def _apply_entry_slippage(price: Decimal, side: str, slippage_pct: Decimal) -> Decimal:
    if side == "LONG":
        return price * (Decimal("1") + slippage_pct)
    return price * (Decimal("1") - slippage_pct)


def _apply_exit_slippage(price: Decimal, side: str, slippage_pct: Decimal) -> Decimal:
    if side == "LONG":
        return price * (Decimal("1") - slippage_pct)
    return price * (Decimal("1") + slippage_pct)
