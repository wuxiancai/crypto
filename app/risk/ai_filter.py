from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AiFilterInput:
    symbol: str
    news_available: bool
    simulated_risk_event: bool


@dataclass(frozen=True)
class AiFilterResult:
    decision: str
    position_multiplier: str
    reason: str
    fallback_reason: str | None = None


@dataclass(frozen=True)
class AiFilterLogEntry:
    provider: str
    input_payload: dict[str, object]
    output_payload: dict[str, str | None]
    fallback_reason: str | None
    evaluated_at: datetime


class AiFilter(Protocol):
    def evaluate(self, filter_input: AiFilterInput) -> AiFilterResult:
        ...


@dataclass(frozen=True)
class DeterministicAiFilter:
    enabled: bool = False

    def evaluate(self, filter_input: AiFilterInput) -> AiFilterResult:
        if not self.enabled:
            return AiFilterResult(
                decision="ALLOW",
                position_multiplier="1",
                reason="ai_filter_disabled",
            )
        if not filter_input.news_available:
            return AiFilterResult(
                decision="BLOCK",
                position_multiplier="0",
                reason="news_unavailable",
                fallback_reason="news_source_failed",
            )
        if filter_input.simulated_risk_event:
            return AiFilterResult(
                decision="BLOCK",
                position_multiplier="0",
                reason="simulated_major_risk_event",
            )
        return AiFilterResult(
            decision="ALLOW",
            position_multiplier="1",
            reason="no_risk_detected",
        )


def build_ai_filter_log_entry(
    filter_input: AiFilterInput,
    result: AiFilterResult,
    provider: str,
    evaluated_at: datetime,
) -> AiFilterLogEntry:
    return AiFilterLogEntry(
        provider=provider,
        input_payload={
            "symbol": filter_input.symbol,
            "news_available": filter_input.news_available,
            "simulated_risk_event": filter_input.simulated_risk_event,
        },
        output_payload={
            "decision": result.decision,
            "position_multiplier": result.position_multiplier,
            "reason": result.reason,
            "fallback_reason": result.fallback_reason,
        },
        fallback_reason=result.fallback_reason,
        evaluated_at=evaluated_at,
    )
