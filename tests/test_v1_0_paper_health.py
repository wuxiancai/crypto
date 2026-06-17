from decimal import Decimal


def test_paper_health_allows_stable_real_market_simulation():
    from app.paper.health import PaperRuntimeSnapshot, evaluate_paper_health

    result = evaluate_paper_health(
        PaperRuntimeSnapshot(
            websocket_connected=True,
            seconds_since_last_kline=5,
            max_kline_delay_seconds=30,
            equity=Decimal("1002"),
            initial_equity=Decimal("1000"),
            max_drawdown_pct=Decimal("0.05"),
            rejected_signals=1,
            max_rejected_signals=10,
            runtime_errors=0,
            max_runtime_errors=0,
        )
    )

    assert result.is_healthy is True
    assert result.status == "HEALTHY"
    assert result.reasons == ()


def test_paper_health_blocks_when_market_data_is_stale():
    from app.paper.health import PaperRuntimeSnapshot, evaluate_paper_health

    result = evaluate_paper_health(
        PaperRuntimeSnapshot.safe_defaults(
            seconds_since_last_kline=120,
            max_kline_delay_seconds=30,
        )
    )

    assert result.is_healthy is False
    assert result.status == "UNHEALTHY"
    assert result.reasons == ("market_data_stale",)


def test_paper_health_reports_drawdown_rejections_and_runtime_errors():
    from app.paper.health import PaperRuntimeSnapshot, evaluate_paper_health

    result = evaluate_paper_health(
        PaperRuntimeSnapshot.safe_defaults(
            equity=Decimal("930"),
            initial_equity=Decimal("1000"),
            max_drawdown_pct=Decimal("0.05"),
            rejected_signals=12,
            max_rejected_signals=10,
            runtime_errors=1,
            max_runtime_errors=0,
        )
    )

    assert result.is_healthy is False
    assert result.status == "UNHEALTHY"
    assert result.reasons == (
        "paper_drawdown_exceeded",
        "too_many_rejected_signals",
        "runtime_errors_present",
    )


def test_paper_health_blocks_when_websocket_disconnected():
    from app.paper.health import PaperRuntimeSnapshot, evaluate_paper_health

    result = evaluate_paper_health(
        PaperRuntimeSnapshot.safe_defaults(websocket_connected=False)
    )

    assert result.is_healthy is False
    assert result.status == "UNHEALTHY"
    assert result.reasons == ("websocket_disconnected",)
