from dataclasses import dataclass
from decimal import Decimal

from app.strategy.position_hierarchy import MarketRegime, SignalScore


@dataclass(frozen=True)
class ControlState:
    market_regime: MarketRegime
    throttle_allows_entry: bool
    equity_guard_allows_entry: bool
    signal_score: SignalScore
    reason: tuple[str, ...] = ()

    @property
    def allows_entry(self) -> bool:
        return self.throttle_allows_entry and self.equity_guard_allows_entry and self.signal_score.passes


def tag_market_regime(
    *,
    fast_ma: Decimal,
    slow_ma: Decimal,
    fast_slope: Decimal = Decimal("0"),
    adx: Decimal | None = None,
    min_adx: Decimal = Decimal("18"),
) -> MarketRegime:
    distance = abs(fast_ma - slow_ma) / slow_ma if slow_ma else Decimal("0")
    if distance < Decimal("0.003"):
        return MarketRegime.TRANSITION
    if adx is not None and adx < min_adx and fast_slope == 0:
        return MarketRegime.RANGE
    if fast_ma > slow_ma:
        return MarketRegime.BULL
    if fast_ma < slow_ma:
        return MarketRegime.BEAR
    return MarketRegime.UNKNOWN


def throttle_allows_entry(
    *,
    bars_since_last_trade: int | None,
    min_bars_between_trades: int,
) -> bool:
    if bars_since_last_trade is None:
        return True
    return bars_since_last_trade >= min_bars_between_trades


def equity_guard_allows_entry(
    *,
    current_equity: Decimal | None,
    peak_equity: Decimal | None,
    max_drawdown_pct: Decimal,
) -> bool:
    if current_equity is None or peak_equity is None or peak_equity <= 0:
        return True
    drawdown = (peak_equity - current_equity) / peak_equity
    return drawdown < max_drawdown_pct


def score_signal(
    *,
    trend_alignment: bool,
    structure_confirmation: bool,
    momentum_confirmation: bool,
    volatility_expansion: bool,
) -> SignalScore:
    components = {
        "trend_alignment": Decimal("35") if trend_alignment else Decimal("0"),
        "structure_confirmation": Decimal("25") if structure_confirmation else Decimal("0"),
        "momentum_confirmation": Decimal("20") if momentum_confirmation else Decimal("0"),
        "volatility_expansion": Decimal("20") if volatility_expansion else Decimal("0"),
    }
    return SignalScore(total=sum(components.values(), Decimal("0")), components=components)


def build_control_state(
    *,
    market_regime: MarketRegime,
    bars_since_last_trade: int | None = None,
    min_bars_between_trades: int = 3,
    current_equity: Decimal | None = None,
    peak_equity: Decimal | None = None,
    max_drawdown_pct: Decimal = Decimal("0.15"),
    trend_alignment: bool,
    structure_confirmation: bool,
    momentum_confirmation: bool,
    volatility_expansion: bool,
) -> ControlState:
    signal_score = score_signal(
        trend_alignment=trend_alignment,
        structure_confirmation=structure_confirmation,
        momentum_confirmation=momentum_confirmation,
        volatility_expansion=volatility_expansion,
    )
    throttle_ok = throttle_allows_entry(
        bars_since_last_trade=bars_since_last_trade,
        min_bars_between_trades=min_bars_between_trades,
    )
    equity_ok = equity_guard_allows_entry(
        current_equity=current_equity,
        peak_equity=peak_equity,
        max_drawdown_pct=max_drawdown_pct,
    )
    reasons: list[str] = []
    if not throttle_ok:
        reasons.append("throttle blocked")
    if not equity_ok:
        reasons.append("equity guard blocked")
    if not signal_score.passes:
        reasons.append(f"signal score below threshold: {signal_score.total}")
    return ControlState(
        market_regime=market_regime,
        throttle_allows_entry=throttle_ok,
        equity_guard_allows_entry=equity_ok,
        signal_score=signal_score,
        reason=tuple(reasons),
    )
