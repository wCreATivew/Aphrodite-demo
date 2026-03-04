from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .schemas import CandidateScore, DecisionType

# Rule thresholds (can be overridden via function args).
NO_TRIGGER_THRESHOLD = 0.25
ASK_CLARIFICATION_MARGIN = 0.08
TRIGGER_THRESHOLD = 0.55
CLARIFY_THRESHOLD = 0.42
MIN_TRIGGER_MARGIN = 0.02


@dataclass
class DecisionOutcome:
    decision: DecisionType
    confidence: float
    margin: float = 0.0
    missing_slots: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    clarification_question: Optional[str] = None
    selected_trigger: Optional[str] = None


def decide(
    *,
    candidates: List[CandidateScore],
    extracted_slots: Dict[str, Any],
    required_slots: List[Dict[str, Any]],
    no_trigger_threshold: float = NO_TRIGGER_THRESHOLD,
    ask_clarification_margin: float = ASK_CLARIFICATION_MARGIN,
    trigger_threshold: float = TRIGGER_THRESHOLD,
    clarify_threshold: float = CLARIFY_THRESHOLD,
    accept_threshold: Optional[float] = None,
    no_trigger_floor: Optional[float] = None,
    min_trigger_margin: float = MIN_TRIGGER_MARGIN,
    low_confidence_threshold: Optional[float] = None,
    margin_threshold: Optional[float] = None,
    per_trigger_accept_threshold: Optional[Dict[str, float]] = None,
    per_trigger_threshold: Optional[Dict[str, float]] = None,
) -> DecisionOutcome:
    if not candidates:
        return DecisionOutcome(
            decision="no_trigger",
            confidence=0.0,
            margin=0.0,
            reasons=["no_candidates"],
        )

    top1 = candidates[0]
    top1_trigger = str(top1.trigger_id or "").strip()
    top1_score = _score_of(top1)
    top2_score = _score_of(candidates[1]) if len(candidates) > 1 else 0.0
    margin = top1_score - top2_score

    # Canonical thresholds.
    floor = float(no_trigger_floor if no_trigger_floor is not None else no_trigger_threshold)
    clarify_cutoff = float(
        clarify_threshold if clarify_threshold is not None else (
            low_confidence_threshold if low_confidence_threshold is not None else CLARIFY_THRESHOLD
        )
    )
    accept_cutoff = float(accept_threshold if accept_threshold is not None else trigger_threshold)
    required_margin = float(margin_threshold if margin_threshold is not None else min_trigger_margin)
    per_trigger_accept = dict(per_trigger_accept_threshold or {})
    if (not per_trigger_accept) and per_trigger_threshold:
        per_trigger_accept = dict(per_trigger_threshold)
    if per_trigger_accept and top1_trigger:
        try:
            accept_cutoff = float(per_trigger_accept.get(top1_trigger, accept_cutoff))
        except Exception:
            accept_cutoff = float(accept_threshold if accept_threshold is not None else trigger_threshold)
    reasons = [
        f"top1_trigger={top1_trigger}",
        f"top1_score={top1_score:.4f}",
        f"top2_score={top2_score:.4f}",
        f"margin={margin:.4f}",
        f"no_trigger_floor={floor:.4f}",
        f"clarify_threshold={clarify_cutoff:.4f}",
        f"accept_threshold={accept_cutoff:.4f}",
        f"margin_threshold={required_margin:.4f}",
    ]

    if top1_score < floor:
        reasons.append("decision=no_trigger_below_floor")
        return DecisionOutcome(
            decision="no_trigger",
            confidence=max(0.0, min(1.0, top1_score)),
            margin=margin,
            reasons=reasons,
        )

    if margin < required_margin or margin < float(ask_clarification_margin):
        reasons.append("decision=ask_clarification_small_margin")
        return DecisionOutcome(
            decision="ask_clarification",
            selected_trigger=top1_trigger,
            confidence=max(0.40, min(1.0, top1_score)),
            margin=margin,
            reasons=reasons,
            clarification_question="I found close intent candidates, please clarify your request.",
        )

    missing = _missing_required_slots(required_slots, extracted_slots)
    if missing:
        reasons.append("decision=ask_clarification_missing_slots")
        return DecisionOutcome(
            decision="ask_clarification",
            selected_trigger=top1_trigger,
            confidence=max(0.40, min(1.0, top1_score)),
            margin=margin,
            missing_slots=missing,
            reasons=reasons,
            clarification_question="Please provide: " + ", ".join(missing),
        )

    if top1_score < clarify_cutoff:
        reasons.append("decision=no_trigger_below_clarify_threshold")
        return DecisionOutcome(
            decision="no_trigger",
            confidence=max(0.0, min(1.0, top1_score)),
            margin=margin,
            reasons=reasons,
        )

    if top1_score < accept_cutoff:
        reasons.append("decision=ask_clarification_mid_confidence")
        return DecisionOutcome(
            decision="ask_clarification",
            selected_trigger=top1_trigger,
            confidence=max(0.40, min(1.0, top1_score)),
            margin=margin,
            reasons=reasons,
            clarification_question="I need one more detail before I execute this action.",
        )

    reasons.append("decision=trigger")
    return DecisionOutcome(
        decision="trigger",
        selected_trigger=top1_trigger,
        confidence=max(accept_cutoff, min(1.0, top1_score)),
        margin=margin,
        reasons=reasons,
    )


def _score_of(c: CandidateScore) -> float:
    if c.final_score is not None:
        return float(c.final_score)
    if c.rerank_score is not None:
        return float(c.rerank_score)
    if c.recall_score is not None:
        return float(c.recall_score)
    return 0.0


def _missing_required_slots(required_slots: List[Dict[str, Any]], extracted: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for slot in required_slots:
        if not isinstance(slot, dict):
            continue
        name = str(slot.get("slot_name") or slot.get("name") or "").strip()
        if not name:
            continue
        required_flag = bool(slot.get("required", True))
        if required_flag and (name not in extracted or extracted.get(name) in {None, ""}):
            out.append(name)
    return out
