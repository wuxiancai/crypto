from decimal import Decimal


def test_small_capital_config_accepts_conservative_live_profile():
    from app.execution.small_capital_config import SmallCapitalLiveConfig, validate_small_capital_config

    result = validate_small_capital_config(
        SmallCapitalLiveConfig(
            profile_name="small_capital_live",
            account_equity_cap=Decimal("1000"),
            risk_per_trade_pct=Decimal("0.005"),
            max_daily_loss_pct=Decimal("0.015"),
            max_leverage=3,
            allowed_symbols=("BTCUSDT", "ETHUSDT"),
            position_mode="ONE_WAY",
            margin_type="ISOLATED",
            live_enabled=True,
        )
    )

    assert result.is_valid is True
    assert result.errors == ()


def test_small_capital_config_rejects_missing_profile_name_and_live_disabled():
    from app.execution.small_capital_config import SmallCapitalLiveConfig, validate_small_capital_config

    result = validate_small_capital_config(
        SmallCapitalLiveConfig.safe_defaults(profile_name="", live_enabled=False)
    )

    assert result.is_valid is False
    assert result.errors == ("invalid_profile_name", "live_profile_not_enabled")


def test_small_capital_config_rejects_aggressive_risk_and_leverage():
    from app.execution.small_capital_config import SmallCapitalLiveConfig, validate_small_capital_config

    result = validate_small_capital_config(
        SmallCapitalLiveConfig.safe_defaults(
            account_equity_cap=Decimal("5000"),
            risk_per_trade_pct=Decimal("0.02"),
            max_daily_loss_pct=Decimal("0.05"),
            max_leverage=6,
        )
    )

    assert result.is_valid is False
    assert result.errors == (
        "account_equity_cap_too_large",
        "risk_per_trade_pct_too_large",
        "max_daily_loss_pct_too_large",
        "max_leverage_too_large",
    )


def test_small_capital_config_rejects_unsupported_symbols_or_execution_mode():
    from app.execution.small_capital_config import SmallCapitalLiveConfig, validate_small_capital_config

    result = validate_small_capital_config(
        SmallCapitalLiveConfig.safe_defaults(
            allowed_symbols=("BTCUSDT", "SOLUSDT"),
            position_mode="HEDGE",
            margin_type="CROSSED",
        )
    )

    assert result.is_valid is False
    assert result.errors == (
        "unsupported_symbols",
        "position_mode_not_one_way",
        "margin_type_not_isolated",
    )
