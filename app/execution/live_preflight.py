from dataclasses import dataclass


@dataclass(frozen=True)
class LivePreflightInput:
    api_has_withdraw_permission: bool
    ip_whitelist_configured: bool
    futures_api_allowed: bool
    server_time_offset_ms: int
    max_server_time_offset_ms: int
    database_migrated: bool
    cache_available_or_degraded: bool
    exchange_rules_synced: bool
    position_mode: str
    margin_type: str
    leverage: int
    max_leverage: int
    has_unknown_positions: bool
    has_unprotected_positions: bool
    stop_order_guard_ok: bool
    liquidation_guard_ok: bool
    max_data_delay_seconds: int
    data_delay_seconds: int
    kill_switch_available: bool
    notification_channel_available: bool
    small_capital_config_loaded: bool
    live_trading_confirm: str

    @classmethod
    def safe_defaults(cls, **overrides: object) -> "LivePreflightInput":
        values = {
            "api_has_withdraw_permission": False,
            "ip_whitelist_configured": True,
            "futures_api_allowed": True,
            "server_time_offset_ms": 500,
            "max_server_time_offset_ms": 1000,
            "database_migrated": True,
            "cache_available_or_degraded": True,
            "exchange_rules_synced": True,
            "position_mode": "ONE_WAY",
            "margin_type": "ISOLATED",
            "leverage": 3,
            "max_leverage": 5,
            "has_unknown_positions": False,
            "has_unprotected_positions": False,
            "stop_order_guard_ok": True,
            "liquidation_guard_ok": True,
            "max_data_delay_seconds": 30,
            "data_delay_seconds": 5,
            "kill_switch_available": True,
            "notification_channel_available": True,
            "small_capital_config_loaded": True,
            "live_trading_confirm": "I_UNDERSTAND_THE_RISK",
        }
        values.update(overrides)
        return cls(**values)


@dataclass(frozen=True)
class LivePreflightResult:
    can_start_live: bool
    failed_checks: tuple[str, ...]


def evaluate_live_preflight(preflight_input: LivePreflightInput) -> LivePreflightResult:
    failed_checks: list[str] = []

    if preflight_input.api_has_withdraw_permission:
        failed_checks.append("api_withdraw_permission_enabled")
    if not preflight_input.ip_whitelist_configured:
        failed_checks.append("ip_whitelist_missing")
    if not preflight_input.futures_api_allowed:
        failed_checks.append("futures_api_not_allowed")
    if abs(preflight_input.server_time_offset_ms) > preflight_input.max_server_time_offset_ms:
        failed_checks.append("server_time_offset_too_large")
    if not preflight_input.database_migrated:
        failed_checks.append("database_not_migrated")
    if not preflight_input.cache_available_or_degraded:
        failed_checks.append("cache_not_available_or_degraded")
    if not preflight_input.exchange_rules_synced:
        failed_checks.append("exchange_rules_not_synced")
    if preflight_input.position_mode != "ONE_WAY":
        failed_checks.append("position_mode_not_one_way")
    if preflight_input.margin_type != "ISOLATED":
        failed_checks.append("margin_type_not_isolated")
    if preflight_input.leverage > preflight_input.max_leverage:
        failed_checks.append("leverage_exceeds_max")
    if preflight_input.has_unknown_positions:
        failed_checks.append("unknown_positions_present")
    if preflight_input.has_unprotected_positions:
        failed_checks.append("unprotected_positions_present")
    if not preflight_input.stop_order_guard_ok:
        failed_checks.append("stop_order_guard_not_ok")
    if not preflight_input.liquidation_guard_ok:
        failed_checks.append("liquidation_guard_not_ok")
    if preflight_input.data_delay_seconds > preflight_input.max_data_delay_seconds:
        failed_checks.append("data_delay_too_large")
    if not preflight_input.kill_switch_available:
        failed_checks.append("kill_switch_unavailable")
    if not preflight_input.notification_channel_available:
        failed_checks.append("notification_channel_unavailable")
    if not preflight_input.small_capital_config_loaded:
        failed_checks.append("small_capital_config_missing")
    if preflight_input.live_trading_confirm != "I_UNDERSTAND_THE_RISK":
        failed_checks.append("live_trading_confirm_missing")

    return LivePreflightResult(
        can_start_live=not failed_checks,
        failed_checks=tuple(failed_checks),
    )
