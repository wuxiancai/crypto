from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SmallCapitalLiveConfig:
    profile_name: str
    account_equity_cap: Decimal
    risk_per_trade_pct: Decimal
    max_daily_loss_pct: Decimal
    max_leverage: int
    allowed_symbols: tuple[str, ...]
    position_mode: str
    margin_type: str
    live_enabled: bool

    @classmethod
    def safe_defaults(cls, **overrides: object) -> "SmallCapitalLiveConfig":
        values = {
            "profile_name": "small_capital_live",
            "account_equity_cap": Decimal("1000"),
            "risk_per_trade_pct": Decimal("0.005"),
            "max_daily_loss_pct": Decimal("0.015"),
            "max_leverage": 10,
            "allowed_symbols": ("BTCUSDT", "ETHUSDT"),
            "position_mode": "ONE_WAY",
            "margin_type": "ISOLATED",
            "live_enabled": True,
        }
        values.update(overrides)
        return cls(**values)


@dataclass(frozen=True)
class SmallCapitalValidationResult:
    is_valid: bool
    errors: tuple[str, ...]


def validate_small_capital_config(
    config: SmallCapitalLiveConfig,
    allowed_symbol_universe: tuple[str, ...] = ("BTCUSDT", "ETHUSDT"),
) -> SmallCapitalValidationResult:
    errors: list[str] = []

    if config.profile_name != "small_capital_live":
        errors.append("invalid_profile_name")
    if not config.live_enabled:
        errors.append("live_profile_not_enabled")
    if config.account_equity_cap > Decimal("1000"):
        errors.append("account_equity_cap_too_large")
    if config.risk_per_trade_pct > Decimal("0.005"):
        errors.append("risk_per_trade_pct_too_large")
    if config.max_daily_loss_pct > Decimal("0.015"):
        errors.append("max_daily_loss_pct_too_large")
    if config.max_leverage > 10:
        errors.append("max_leverage_too_large")
    if any(symbol not in allowed_symbol_universe for symbol in config.allowed_symbols):
        errors.append("unsupported_symbols")
    if config.position_mode != "ONE_WAY":
        errors.append("position_mode_not_one_way")
    if config.margin_type != "ISOLATED":
        errors.append("margin_type_not_isolated")

    return SmallCapitalValidationResult(is_valid=not errors, errors=tuple(errors))
