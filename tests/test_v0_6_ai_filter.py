def test_ai_filter_stub_allows_when_disabled_and_no_forced_risk():
    from app.risk.ai_filter import AiFilterInput, DeterministicAiFilter

    result = DeterministicAiFilter(enabled=False).evaluate(
        AiFilterInput(symbol="BTCUSDT", news_available=True, simulated_risk_event=False)
    )

    assert result.decision == "ALLOW"
    assert result.position_multiplier == "1"
    assert result.reason == "ai_filter_disabled"
    assert result.fallback_reason is None


def test_ai_filter_stub_blocks_when_news_is_unavailable():
    from app.risk.ai_filter import AiFilterInput, DeterministicAiFilter

    result = DeterministicAiFilter(enabled=True).evaluate(
        AiFilterInput(symbol="BTCUSDT", news_available=False, simulated_risk_event=False)
    )

    assert result.decision == "BLOCK"
    assert result.position_multiplier == "0"
    assert result.reason == "news_unavailable"
    assert result.fallback_reason == "news_source_failed"


def test_ai_filter_stub_blocks_simulated_major_risk_event():
    from app.risk.ai_filter import AiFilterInput, DeterministicAiFilter

    result = DeterministicAiFilter(enabled=True).evaluate(
        AiFilterInput(symbol="ETHUSDT", news_available=True, simulated_risk_event=True)
    )

    assert result.decision == "BLOCK"
    assert result.position_multiplier == "0"
    assert result.reason == "simulated_major_risk_event"
    assert result.fallback_reason is None
