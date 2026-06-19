def test_live_preflight_allows_start_when_all_required_checks_pass():
    from app.execution.live_preflight import LivePreflightInput, evaluate_live_preflight

    result = evaluate_live_preflight(
        LivePreflightInput(
            api_has_withdraw_permission=False,
            ip_whitelist_configured=True,
            futures_api_allowed=True,
            server_time_offset_ms=500,
            max_server_time_offset_ms=1000,
            database_migrated=True,
            cache_available_or_degraded=True,
            exchange_rules_synced=True,
            position_mode="ONE_WAY",
            margin_type="ISOLATED",
            leverage=10,
            max_leverage=10,
            has_unknown_positions=False,
            has_unprotected_positions=False,
            stop_order_guard_ok=True,
            liquidation_guard_ok=True,
            max_data_delay_seconds=30,
            data_delay_seconds=5,
            kill_switch_available=True,
            notification_channel_available=True,
            small_capital_config_loaded=True,
            live_trading_confirm="I_UNDERSTAND_THE_RISK",
        )
    )

    assert result.can_start_live is True
    assert result.failed_checks == ()


def test_live_preflight_blocks_when_api_key_can_withdraw():
    from app.execution.live_preflight import LivePreflightInput, evaluate_live_preflight

    result = evaluate_live_preflight(
        LivePreflightInput.safe_defaults(api_has_withdraw_permission=True)
    )

    assert result.can_start_live is False
    assert "api_withdraw_permission_enabled" in result.failed_checks


def test_live_preflight_blocks_when_execution_mode_is_not_mvp_default():
    from app.execution.live_preflight import LivePreflightInput, evaluate_live_preflight

    result = evaluate_live_preflight(
        LivePreflightInput.safe_defaults(position_mode="HEDGE", margin_type="CROSSED")
    )

    assert result.can_start_live is False
    assert result.failed_checks == ("position_mode_not_one_way", "margin_type_not_isolated")


def test_live_preflight_blocks_when_guards_or_confirmation_are_missing():
    from app.execution.live_preflight import LivePreflightInput, evaluate_live_preflight

    result = evaluate_live_preflight(
        LivePreflightInput.safe_defaults(
            stop_order_guard_ok=False,
            liquidation_guard_ok=False,
            live_trading_confirm="",
        )
    )

    assert result.can_start_live is False
    assert result.failed_checks == (
        "stop_order_guard_not_ok",
        "liquidation_guard_not_ok",
        "live_trading_confirm_missing",
    )
