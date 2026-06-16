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
    maker_fee_rate: Decimal | None = None
    taker_fee_rate: Decimal | None = None
    default_stop_distance_pct: Decimal = Decimal("0.02")
    default_take_profit_risk_reward: Decimal = Decimal("2")


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
    metrics: "BacktestMetrics"


@dataclass(frozen=True)
class StrategyMetrics:
    total_trades: int
    wins: int
    losses: int
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal


@dataclass(frozen=True)
class BacktestMetrics:
    total_trades: int
    wins: int
    losses: int
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    by_strategy: dict[str, StrategyMetrics]


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
    entry_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None


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
        if position is None and signal.action in {"LONG_ENTRY", "SHORT_ENTRY", "REVERSAL_LONG_ENTRY", "REVERSAL_SHORT_ENTRY"}:
            position = _open_position(kline, signal, equity, config)

    return BacktestResult(
        initial_equity=config.initial_equity,
        final_equity=equity,
        trades=trades,
        metrics=_build_metrics(trades),
    )


def _open_position(kline: Kline, signal: SignalLike, equity: Decimal, config: BacktestConfig) -> _Position:
    side = _side_from_action(signal.action)
    raw_entry_price = getattr(signal, "entry_price", None) or kline.close
    stop_loss = getattr(signal, "stop_loss", None) or _default_stop_loss(raw_entry_price, side, config)
    take_profit = getattr(signal, "take_profit", None) or _default_take_profit(raw_entry_price, stop_loss, side, config)

    entry_price = _apply_entry_slippage(raw_entry_price, side, config.slippage_pct)
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0:
        raise ValueError("stop distance must be positive")

    risk_pct = getattr(signal, "risk_pct", None) or config.risk_per_trade_pct
    risk_amount = equity * risk_pct
    quantity = risk_amount / stop_distance
    entry_fee = entry_price * quantity * _taker_fee_rate(config)
    return _Position(
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


def _side_from_action(action: str) -> str:
    if action in {"LONG_ENTRY", "REVERSAL_LONG_ENTRY"}:
        return "LONG"
    if action in {"SHORT_ENTRY", "REVERSAL_SHORT_ENTRY"}:
        return "SHORT"
    raise ValueError(f"unsupported entry action: {action}")


def _default_stop_loss(entry_price: Decimal, side: str, config: BacktestConfig) -> Decimal:
    if side == "LONG":
        return entry_price * (Decimal("1") - config.default_stop_distance_pct)
    return entry_price * (Decimal("1") + config.default_stop_distance_pct)


def _default_take_profit(entry_price: Decimal, stop_loss: Decimal, side: str, config: BacktestConfig) -> Decimal:
    risk = abs(entry_price - stop_loss)
    if side == "LONG":
        return entry_price + risk * config.default_take_profit_risk_reward
    return entry_price - risk * config.default_take_profit_risk_reward


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
    exit_fee = exit_price * position.quantity * _exit_fee_rate(exit_reason, config)
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


def _maker_fee_rate(config: BacktestConfig) -> Decimal:
    return config.maker_fee_rate if config.maker_fee_rate is not None else config.fee_rate


def _taker_fee_rate(config: BacktestConfig) -> Decimal:
    return config.taker_fee_rate if config.taker_fee_rate is not None else config.fee_rate


def _exit_fee_rate(exit_reason: str, config: BacktestConfig) -> Decimal:
    if exit_reason == "TAKE_PROFIT":
        return _maker_fee_rate(config)
    return _taker_fee_rate(config)


def _build_metrics(trades: list[BacktestTrade]) -> BacktestMetrics:
    by_strategy: dict[str, StrategyMetrics] = {}
    for strategy_type in sorted({trade.strategy_type for trade in trades}):
        strategy_trades = [trade for trade in trades if trade.strategy_type == strategy_type]
        by_strategy[strategy_type] = _strategy_metrics(strategy_trades)
    overall = _strategy_metrics(trades)
    return BacktestMetrics(
        total_trades=overall.total_trades,
        wins=overall.wins,
        losses=overall.losses,
        gross_pnl=overall.gross_pnl,
        fees=overall.fees,
        net_pnl=overall.net_pnl,
        by_strategy=by_strategy,
    )


def _strategy_metrics(trades: list[BacktestTrade]) -> StrategyMetrics:
    return StrategyMetrics(
        total_trades=len(trades),
        wins=sum(1 for trade in trades if trade.net_pnl > 0),
        losses=sum(1 for trade in trades if trade.net_pnl < 0),
        gross_pnl=sum((trade.gross_pnl for trade in trades), Decimal("0")),
        fees=sum((trade.fees for trade in trades), Decimal("0")),
        net_pnl=sum((trade.net_pnl for trade in trades), Decimal("0")),
    )
