from datetime import datetime, timezone


def test_builds_ai_filter_log_entry_with_input_output_and_fallback_reason():
    from app.risk.ai_filter import AiFilterInput, AiFilterResult, build_ai_filter_log_entry

    evaluated_at = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)

    log_entry = build_ai_filter_log_entry(
        filter_input=AiFilterInput(
            symbol="BTCUSDT",
            news_available=False,
            simulated_risk_event=False,
        ),
        result=AiFilterResult(
            decision="BLOCK",
            position_multiplier="0",
            reason="news_unavailable",
            fallback_reason="news_source_failed",
        ),
        provider="deterministic_stub",
        evaluated_at=evaluated_at,
    )

    assert log_entry.provider == "deterministic_stub"
    assert log_entry.input_payload == {
        "symbol": "BTCUSDT",
        "news_available": False,
        "simulated_risk_event": False,
    }
    assert log_entry.output_payload == {
        "decision": "BLOCK",
        "position_multiplier": "0",
        "reason": "news_unavailable",
        "fallback_reason": "news_source_failed",
    }
    assert log_entry.fallback_reason == "news_source_failed"
    assert log_entry.evaluated_at == evaluated_at
