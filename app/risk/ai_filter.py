from dataclasses import dataclass
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
