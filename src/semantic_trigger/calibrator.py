from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import AppConfig
from .constraints import ConstraintCheckResult
from .decision import decide as rule_decide
from .schemas import CandidateScore, DecisionType, TriggerDef


@dataclass(frozen=True)
class CalibrationDecision:
    decision: DecisionType
    selected_trigger: Optional[str]
    confidence: float
    reasons: List[str]


def decide(
    *,
    query: str,
    ranked: List[CandidateScore],
    trigger: Optional[TriggerDef],
    config: AppConfig,
    missing_slots: List[str],
    constraint_result: ConstraintCheckResult,
) -> CalibrationDecision:
    if not ranked or trigger is None:
        return CalibrationDecision(
            decision="no_trigger",
            selected_trigger=None,
            confidence=0.0,
            reasons=["no_candidates"],
        )

    top1 = float(ranked[0].final_score or 0.0)
    reasons: List[str] = [f"calibrator_query={str(query or '')[:120]}"]

    if not constraint_result.ok:
        reasons.append(f"constraint_failed={','.join(constraint_result.failed)}")
        return CalibrationDecision(
            decision="no_trigger",
            selected_trigger=None,
            confidence=max(0.0, top1 * 0.4),
            reasons=reasons,
        )

    extracted_slots = {}
    required_slots = [{"slot_name": str(s), "required": True} for s in list(missing_slots or [])]

    outcome = rule_decide(
        candidates=ranked,
        extracted_slots=extracted_slots,
        required_slots=required_slots,
        no_trigger_floor=float(config.no_trigger_floor),
        clarify_threshold=float(config.clarify_threshold),
        accept_threshold=float(config.accept_threshold),
        margin_threshold=float(config.margin_threshold),
        no_trigger_threshold=float(config.no_trigger_threshold),
        ask_clarification_margin=float(config.ask_clarification_margin),
        trigger_threshold=float(config.trigger_threshold),
        low_confidence_threshold=float(config.low_confidence_threshold),
        per_trigger_accept_threshold=dict(config.per_trigger_accept_threshold or {}),
        per_trigger_threshold=dict(config.per_trigger_threshold or {}),
    )
    reasons.extend(list(outcome.reasons))
    return CalibrationDecision(
        decision=outcome.decision,
        selected_trigger=outcome.selected_trigger,
        confidence=float(outcome.confidence),
        reasons=reasons,
    )
