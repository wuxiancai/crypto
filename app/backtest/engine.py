from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from app.data.quality import Kline


@dataclass(frozen=True)
class FundingRate:
    symbol: str
    funding_time: int
    rate: Decimal


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: Decimal
    risk_per_trade_pct: Decimal
    fee_rate: Decimal
    slippage_pct: Decimal
    stop_slippage_pct: Decimal | None = None
    maker_fee_rate: Decimal | None = None
    taker_fee_rate: Decimal | None = None
    default_stop_distance_pct: Decimal = Decimal("0.02")
    default_take_profit_risk_reward: Decimal = Decimal("2")
    quantity_step: Decimal | None = None
    min_qty: Decimal | None = None
    min_notional: Decimal | None = None
    funding_rates: list[FundingRate] | None = None
    price_tick: Decimal | None = None


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
    funding_fee: Decimal
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
    funding_fees: Decimal
    net_pnl: Decimal


@dataclass(frozen=True)
class BacktestMetrics:
    total_trades: int
    wins: int
    losses: int
    gross_pnl: Decimal
    fees: Decimal
    funding_fees: Decimal
    net_pnl: Decimal
    rejected_entries: int
    unfilled_entries: int
    partial_fills: int
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
    is_partial_fill: bool = False


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
    rejected_entries = 0
    unfilled_entries = 0
    partial_fills = 0

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
            if _is_unfilled_limit(kline, signal):
                unfilled_entries += 1
                continue
            position = _open_position(kline, signal, equity, config)
            if position is None:
                rejected_entries += 1
            elif position.is_partial_fill:
                partial_fills += 1

    return BacktestResult(
        initial_equity=config.initial_equity,
        final_equity=equity,
        trades=trades,
        metrics=_build_metrics(
            trades,
            rejected_entries=rejected_entries,
            unfilled_entries=unfilled_entries,
            partial_fills=partial_fills,
        ),
    )


def _open_position(kline: Kline, signal: SignalLike, equity: Decimal, config: BacktestConfig) -> _Position | None:
    side = _side_from_action(signal.action)
    raw_entry_price = getattr(signal, "entry_price", None) or kline.close
    stop_loss = getattr(signal, "stop_loss", None) or _default_stop_loss(raw_entry_price, side, config)
    take_profit = getattr(signal, "take_profit", None) or _default_take_profit(raw_entry_price, stop_loss, side, config)

    entry_price = _round_price_for_side(_apply_entry_slippage(raw_entry_price, side, config.slippage_pct), side, config)
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0:
        raise ValueError("stop distance must be positive")

    risk_pct = getattr(signal, "risk_pct", None) or config.risk_per_trade_pct
    risk_amount = equity * risk_pct
    quantity = _apply_quantity_step(risk_amount / stop_distance, config)
    fill_ratio = _fill_ratio(signal)
    quantity = quantity * fill_ratio
    if _violates_exchange_filters(quantity, entry_price, config):
        return None
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
        is_partial_fill=fill_ratio < Decimal("1"),
    )


def _is_unfilled_limit(kline: Kline, signal: SignalLike) -> bool:
    if getattr(signal, "order_type", "MARKET") != "LIMIT":
        return False
    side = _side_from_action(signal.action)
    entry_price = getattr(signal, "entry_price", None) or kline.close
    if side == "LONG":
        return kline.low > entry_price
    return kline.high < entry_price


def _fill_ratio(signal: SignalLike) -> Decimal:
    ratio = getattr(signal, "fill_ratio", Decimal("1"))
    return min(max(ratio, Decimal("0")), Decimal("1"))


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
            raw_exit_price = min(kline.open, position.stop_loss)
            return _close_position(position, kline, raw_exit_price, "STOP_LOSS", config)
        if kline.high >= position.take_profit:
            return _close_position(position, kline, position.take_profit, "TAKE_PROFIT", config)
        return None

    if kline.high >= position.stop_loss:
        raw_exit_price = max(kline.open, position.stop_loss)
        return _close_position(position, kline, raw_exit_price, "STOP_LOSS", config)
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
    exit_price = _round_price_for_side(
        _apply_exit_slippage(raw_exit_price, position.side, _exit_slippage_pct(exit_reason, config)),
        "SHORT" if position.side == "LONG" else "LONG",
        config,
    )
    if position.side == "LONG":
        gross_pnl = (exit_price - position.entry_price) * position.quantity
    else:
        gross_pnl = (position.entry_price - exit_price) * position.quantity
    exit_fee = exit_price * position.quantity * _exit_fee_rate(exit_reason, config)
    fees = position.entry_fee + exit_fee
    funding_fee = _funding_fee(position, kline.close_time, config)
    net_pnl = gross_pnl - fees - funding_fee
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
        funding_fee=funding_fee,
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


def _round_price_for_side(price: Decimal, side: str, config: BacktestConfig) -> Decimal:
    if config.price_tick is None:
        return price
    if side == "LONG":
        return _ceil_to_step(price, config.price_tick)
    return _floor_to_step(price, config.price_tick)


def _exit_slippage_pct(exit_reason: str, config: BacktestConfig) -> Decimal:
    if exit_reason == "STOP_LOSS" and config.stop_slippage_pct is not None:
        return config.stop_slippage_pct
    return config.slippage_pct


def _maker_fee_rate(config: BacktestConfig) -> Decimal:
    return config.maker_fee_rate if config.maker_fee_rate is not None else config.fee_rate


def _taker_fee_rate(config: BacktestConfig) -> Decimal:
    return config.taker_fee_rate if config.taker_fee_rate is not None else config.fee_rate


def _exit_fee_rate(exit_reason: str, config: BacktestConfig) -> Decimal:
    if exit_reason == "TAKE_PROFIT":
        return _maker_fee_rate(config)
    return _taker_fee_rate(config)


def _funding_fee(position: _Position, exit_time: int, config: BacktestConfig) -> Decimal:
    if not config.funding_rates:
        return Decimal("0")
    funding_fee = Decimal("0")
    notional = position.entry_price * position.quantity
    for funding_rate in config.funding_rates:
        if funding_rate.symbol != position.symbol:
            continue
        if position.entry_time < funding_rate.funding_time <= exit_time:
            signed_fee = notional * funding_rate.rate
            funding_fee += signed_fee if position.side == "LONG" else -signed_fee
    return funding_fee


def _apply_quantity_step(quantity: Decimal, config: BacktestConfig) -> Decimal:
    if config.quantity_step is None:
        return quantity
    return (quantity // config.quantity_step) * config.quantity_step


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value // step) * step


def _ceil_to_step(value: Decimal, step: Decimal) -> Decimal:
    floored = _floor_to_step(value, step)
    if floored == value:
        return value
    return floored + step


def _violates_exchange_filters(quantity: Decimal, price: Decimal, config: BacktestConfig) -> bool:
    if config.min_qty is not None and quantity < config.min_qty:
        return True
    if config.min_notional is not None and quantity * price < config.min_notional:
        return True
    return False


def _build_metrics(
    trades: list[BacktestTrade],
    rejected_entries: int = 0,
    unfilled_entries: int = 0,
    partial_fills: int = 0,
) -> BacktestMetrics:
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
        funding_fees=overall.funding_fees,
        net_pnl=overall.net_pnl,
        rejected_entries=rejected_entries,
        unfilled_entries=unfilled_entries,
        partial_fills=partial_fills,
        by_strategy=by_strategy,
    )


def _strategy_metrics(trades: list[BacktestTrade]) -> StrategyMetrics:
    return StrategyMetrics(
        total_trades=len(trades),
        wins=sum(1 for trade in trades if trade.net_pnl > 0),
        losses=sum(1 for trade in trades if trade.net_pnl < 0),
        gross_pnl=sum((trade.gross_pnl for trade in trades), Decimal("0")),
        fees=sum((trade.fees for trade in trades), Decimal("0")),
        funding_fees=sum((trade.funding_fee for trade in trades), Decimal("0")),
        net_pnl=sum((trade.net_pnl for trade in trades), Decimal("0")),
    )
