from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from .schemas import CandidateScore, DecisionType


@dataclass(frozen=True)
class AdjudicationResult:
    decision: DecisionType
    selected_trigger: Optional[str]
    confidence: float
    reason: str


class Adjudicator(Protocol):
    def adjudicate(
        self,
        *,
        query: str,
        candidates: List[CandidateScore],
        summary: Dict[str, float],
        context: Dict[str, str],
    ) -> AdjudicationResult: ...


@dataclass
class MockAdjudicator:
    def adjudicate(
        self,
        *,
        query: str,
        candidates: List[CandidateScore],
        summary: Dict[str, float],
        context: Dict[str, str],
    ) -> AdjudicationResult:
        if not candidates:
            return AdjudicationResult(
                decision="no_trigger",
                selected_trigger=None,
                confidence=0.0,
                reason="mock:no_candidates",
            )
        top1 = candidates[0]
        margin = float(summary.get("margin", 0.0))
        top_score = float(top1.final_score or 0.0)
        if top_score >= 0.62 and margin >= 0.04:
            return AdjudicationResult(
                decision="trigger",
                selected_trigger=top1.trigger_id,
                confidence=float(min(0.95, top_score + margin)),
                reason="mock:promote_trigger",
            )
        return AdjudicationResult(
            decision="ask_clarification",
            selected_trigger=top1.trigger_id,
            confidence=float(max(0.45, top_score)),
            reason="mock:ask_clarification",
        )
