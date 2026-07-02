from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class StrategyKernel(str, Enum):
    WEEKLY_DAILY_H4_V1 = "WEEKLY_DAILY_H4_V1"


TRADE_POLICY_VERSION = "INDEPENDENT_TIMELINES_V2"


class PositionLevel(str, Enum):
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"
    H4 = "H4"


class TradeMode(str, Enum):
    TREND = "TREND"
    REBOUND = "REBOUND"
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    CONTINUATION = "CONTINUATION"


class MarketRegime(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


class LifecycleState(str, Enum):
    PLANNED = "PLANNED"
    OPEN = "OPEN"
    REDUCING = "REDUCING"
    PROTECTED = "PROTECTED"
    EXITING = "EXITING"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class KernelPositionRef:
    symbol: str
    side: str
    position_level: PositionLevel
    trade_mode: TradeMode
    lifecycle_state: LifecycleState = LifecycleState.OPEN


@dataclass(frozen=True)
class SignalScore:
    total: Decimal
    components: dict[str, Decimal] = field(default_factory=dict)

    @property
    def passes(self) -> bool:
        return self.total >= Decimal("70")


def legacy_bucket_to_position_level(bucket: str | None) -> None:
    return None


def normalise_position_level(value: str | PositionLevel | None) -> PositionLevel | None:
    if isinstance(value, PositionLevel):
        return value
    if value is None:
        return None
    try:
        return PositionLevel(str(value).upper())
    except ValueError:
        return None


def normalise_trade_mode(value: str | TradeMode | None) -> TradeMode | None:
    if isinstance(value, TradeMode):
        return value
    if value is None:
        return None
    try:
        return TradeMode(str(value).upper())
    except ValueError:
        return None
