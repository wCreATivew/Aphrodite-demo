from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from .config import EngineConfig
from .decision import decide
from .logging_utils import get_logger
from .registry import TriggerRegistry
from .schemas import CandidateScore, EngineResult, TriggerDef

try:
    from .clarify import build_clarification_question as _build_slot_question
except Exception:
    _build_slot_question = None
try:
    from .clarify import build_clarification_question_v2 as _build_slot_question_v2
except Exception:
    _build_slot_question_v2 = None

try:
    from .retriever import CandidateRetriever as _DefaultRetriever
except Exception:
    _DefaultRetriever = None

try:
    from .reranker import BaselineReranker as _DefaultReranker
except Exception:
    _DefaultReranker = None

try:
    from .slot_extractor import RuleSlotExtractor as _DefaultSlotExtractor
except Exception:
    _DefaultSlotExtractor = None


class RetrieverLike(Protocol):
    def retrieve(self, query: str, triggers: List[TriggerDef], top_k: int) -> List[CandidateScore]: ...


class RerankerLike(Protocol):
    def rerank(self, query: str, candidates: List[CandidateScore], triggers_by_id: Dict[str, TriggerDef]) -> List[CandidateScore]: ...


class SlotExtractorLike(Protocol):
    def extract(self, query: str, trigger: TriggerDef) -> Dict[str, Any]: ...


@dataclass
class SemanticTriggerEngine:
    triggers: List[TriggerDef] = field(default_factory=list)
    config: EngineConfig = field(default_factory=EngineConfig)
    retriever: Optional[Any] = None
    reranker: Optional[Any] = None
    slot_extractor: Optional[Any] = None
    registry: Optional[TriggerRegistry] = None
    logger: Optional[Any] = None

    @staticmethod
    def build_default(registry: TriggerRegistry, config: EngineConfig) -> "SemanticTriggerEngine":
        retriever = _DefaultRetriever() if _DefaultRetriever is not None else None
        reranker = _DefaultReranker() if _DefaultReranker is not None else None
        slot_extractor = _DefaultSlotExtractor() if _DefaultSlotExtractor is not None else None
        return SemanticTriggerEngine(
            triggers=list(registry.triggers),
            config=config,
            registry=registry,
            retriever=retriever,
            reranker=reranker,
            slot_extractor=slot_extractor,
            logger=get_logger("semantic_trigger.engine", level=config.log_level, json_log=config.json_log),
        )

    def predict(self, query: str, debug: bool = False) -> EngineResult:
        return self._predict_internal(query=query, debug=debug, top_k=int(self.config.top_k))

    # Compatibility entrypoint used by existing integrations.
    def infer(self, query: str, top_k: Optional[int] = None) -> EngineResult:
        k = int(top_k) if top_k is not None else int(self.config.top_k)
        # Keep key intermediate metrics for runtime/monitor even without verbose mode.
        return self._predict_internal(query=query, debug=False, top_k=k)

    def _predict_internal(self, *, query: str, debug: bool, top_k: int) -> EngineResult:
        q = str(query or "").strip()
        all_triggers = self._resolve_triggers()

        if not q:
            return EngineResult(
                user_query=q,
                decision="no_trigger",
                selected_trigger=None,
                confidence=0.0,
                reasons=["empty_query"],
                debug=self._minimal_debug_payload(top1=0.0, top2=0.0, margin=0.0),
            )
        if not all_triggers:
            return EngineResult(
                user_query=q,
                decision="no_trigger",
                selected_trigger=None,
                confidence=0.0,
                reasons=["no_triggers_available"],
                debug=self._minimal_debug_payload(top1=0.0, top2=0.0, margin=0.0),
            )

        candidates = self._run_retriever(q, all_triggers, top_k=max(1, int(top_k)))
        candidates = self._run_reranker(q, candidates, {t.trigger_id: t for t in all_triggers})
        candidates = sorted(candidates, key=lambda c: float(c.final_score or 0.0), reverse=True)
        candidates = candidates[: max(1, int(top_k))]

        top1 = float(candidates[0].final_score or 0.0) if candidates else 0.0
        top2 = float(candidates[1].final_score or 0.0) if len(candidates) > 1 else 0.0
        margin = top1 - top2

        top = candidates[0] if candidates else None
        top_trigger = self._find_trigger(all_triggers, top.trigger_id if top else "")
        extracted_slots = self._run_slot_extractor(q, top_trigger)

        decision_out = decide(
            candidates=candidates,
            extracted_slots=extracted_slots,
            required_slots=list(top_trigger.required_slots) if top_trigger else [],
            no_trigger_floor=self.config.no_trigger_floor,
            clarify_threshold=self.config.clarify_threshold,
            accept_threshold=self.config.accept_threshold,
            no_trigger_threshold=self.config.no_trigger_threshold,
            ask_clarification_margin=self.config.ask_clarification_margin,
            trigger_threshold=self.config.trigger_threshold,
            min_trigger_margin=self.config.min_trigger_margin,
            low_confidence_threshold=self.config.low_confidence_threshold,
            margin_threshold=self.config.margin_threshold,
            per_trigger_accept_threshold=self.config.per_trigger_accept_threshold,
            per_trigger_threshold=self.config.per_trigger_threshold,
        )

        selected_trigger = decision_out.selected_trigger if decision_out.decision != "no_trigger" else None
        clarification_question = self._resolve_clarification(
            decision=decision_out.decision,
            incoming_question=decision_out.clarification_question,
            missing_slots=decision_out.missing_slots,
            selected_trigger=str(decision_out.selected_trigger or ""),
            candidates=candidates,
        )

        return EngineResult(
            user_query=q,
            decision=decision_out.decision,
            selected_trigger=selected_trigger,
            confidence=float(max(0.0, min(1.0, decision_out.confidence))),
            candidates=candidates,
            extracted_slots=extracted_slots if decision_out.decision != "no_trigger" else {},
            missing_slots=list(decision_out.missing_slots),
            clarification_question=clarification_question,
            reasons=list(decision_out.reasons),
            debug=self._debug_payload(
                verbose=debug,
                query=q,
                candidates=candidates,
                extracted_slots=extracted_slots,
                top_trigger=top_trigger,
                top1=top1,
                top2=top2,
                margin=margin,
            ),
        )

    def _resolve_triggers(self) -> List[TriggerDef]:
        src = self.registry.triggers if self.registry is not None else self.triggers
        if self.config.keep_disabled:
            return list(src)
        return [t for t in src if t.enabled]

    def _run_retriever(self, query: str, triggers: List[TriggerDef], top_k: int) -> List[CandidateScore]:
        if self.retriever is None:
            return _StubRetriever().retrieve(query, triggers, top_k=top_k)

        if hasattr(self.retriever, "retrieve"):
            try:
                out = self.retriever.retrieve(query, triggers, top_k)
            except TypeError:
                out = self.retriever.retrieve(query=query, triggers=triggers, top_k=top_k)
            return _normalize_candidates(out, triggers)

        if hasattr(self.retriever, "recall"):
            try:
                out = self.retriever.recall(query, triggers, top_k=top_k)
            except TypeError:
                out = self.retriever.recall(query=query, triggers=triggers, top_k=top_k)
            return _normalize_candidates(out, triggers)

        return _StubRetriever().retrieve(query, triggers, top_k=top_k)

    def _run_reranker(
        self,
        query: str,
        candidates: List[CandidateScore],
        by_id: Dict[str, TriggerDef],
    ) -> List[CandidateScore]:
        if not candidates:
            return []
        if self.reranker is None:
            return _PassthroughReranker().rerank(query, candidates, by_id)

        if hasattr(self.reranker, "rerank"):
            try:
                out = self.reranker.rerank(query, candidates, by_id)
            except TypeError:
                out = self.reranker.rerank(query, candidates)
            return _normalize_candidates(out, list(by_id.values()))
        return _PassthroughReranker().rerank(query, candidates, by_id)

    def _run_slot_extractor(self, query: str, trigger: Optional[TriggerDef]) -> Dict[str, Any]:
        if trigger is None:
            return {}
        if self.slot_extractor is None:
            return _StubSlotExtractor().extract(query, trigger)

        if hasattr(self.slot_extractor, "extract"):
            # Prefer dict-shaped trigger for maximum compatibility with slot_extractors
            # that expect protocol-style slot dicts.
            trigger_payload = _trigger_to_dict(trigger)
            try:
                out = self.slot_extractor.extract(query, trigger_payload)
            except Exception:
                try:
                    out = self.slot_extractor.extract(query, trigger)
                except Exception:
                    return {}

            if isinstance(out, dict):
                return dict(out)
            if hasattr(out, "extracted_slots"):
                raw = getattr(out, "extracted_slots")
                if isinstance(raw, dict):
                    return dict(raw)
            if hasattr(out, "extracted"):
                raw = getattr(out, "extracted")
                if isinstance(raw, dict):
                    return dict(raw)
        return {}

    def _resolve_clarification(
        self,
        *,
        decision: str,
        incoming_question: Optional[str],
        missing_slots: List[str],
        selected_trigger: str,
        candidates: List[CandidateScore],
    ) -> Optional[str]:
        if decision != "ask_clarification":
            return None
        incoming_text = str(incoming_question or "").strip()
        incoming_low = incoming_text.lower()
        incoming_is_generic = (
            ("please provide" in incoming_low)
            or ("multiple possible intents" in incoming_low)
            or ("need more detail" in incoming_low)
        )
        if incoming_text and (not incoming_is_generic):
            return incoming_question
        if _build_slot_question_v2 is not None:
            try:
                q = _build_slot_question_v2(
                    missing_slots=missing_slots,
                    candidate_names=[c.name or c.trigger_id for c in candidates[:2]],
                )
                if q:
                    return str(q)
            except Exception:
                pass
        if _build_slot_question is not None:
            try:
                q = _build_slot_question(
                    missing_slots,
                    selected_trigger=str(selected_trigger or ""),
                    candidate_names=[c.name or c.trigger_id for c in candidates[:2]],
                )
                if q:
                    return str(q)
            except Exception:
                pass
        if incoming_text:
            return incoming_question
        if len(candidates) >= 2:
            left = candidates[0].name or candidates[0].trigger_id
            right = candidates[1].name or candidates[1].trigger_id
            return f"Did you mean '{left}' or '{right}'?"
        return "Please provide more detail so I can choose the right action."

    def _minimal_debug_payload(self, *, top1: float, top2: float, margin: float) -> Dict[str, Any]:
        return {
            "top1_score": float(top1),
            "top2_score": float(top2),
            "margin": float(margin),
            "top_k_candidates": [],
            "recall_scores": {},
            "rerank_scores": {},
            "config_version": str(self.config.config_version),
            "policy_version": str(self.config.policy_version),
            "dataset_version": str(self.config.dataset_version),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _debug_payload(
        self,
        *,
        verbose: bool,
        query: str,
        candidates: List[CandidateScore],
        extracted_slots: Dict[str, Any],
        top_trigger: Optional[TriggerDef],
        top1: float,
        top2: float,
        margin: float,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "top1_score": top1,
            "top2_score": top2,
            "margin": margin,
            "config_version": str(self.config.config_version),
            "policy_version": str(self.config.policy_version),
            "dataset_version": str(self.config.dataset_version),
            "top_k_candidates": [
                c.trigger_id for c in candidates[: max(1, int(self.config.top_k))]
            ],
            "recall_scores": {
                c.trigger_id: float(c.recall_score or 0.0)
                for c in candidates[: max(1, int(self.config.top_k))]
            },
            "rerank_scores": {
                c.trigger_id: float(c.rerank_score or 0.0)
                for c in candidates[: max(1, int(self.config.top_k))]
            },
            "config_version": str(self.config.config_version),
            "policy_version": str(self.config.policy_version),
            "dataset_version": str(self.config.dataset_version),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not verbose:
            return payload

        rows = [
            {
                "trigger_id": c.trigger_id,
                "name": c.name,
                "recall_score": c.recall_score,
                "rerank_score": c.rerank_score,
                "final_score": c.final_score,
                "notes": c.notes,
            }
            for c in candidates
        ]
        payload.update(
            {
                "query": query,
                "candidate_count": len(candidates),
                "candidates": rows,
                "extracted_slots": dict(extracted_slots),
                "thresholds": {
                    "accept_threshold": self.config.accept_threshold,
                    "clarify_threshold": self.config.clarify_threshold,
                    "no_trigger_floor": self.config.no_trigger_floor,
                    "no_trigger_threshold": self.config.no_trigger_threshold,
                    "ask_clarification_margin": self.config.ask_clarification_margin,
                    "trigger_threshold": self.config.trigger_threshold,
                    "min_trigger_margin": self.config.min_trigger_margin,
                    "margin_threshold": self.config.margin_threshold,
                },
                "top_trigger_required_slots": list(top_trigger.required_slots) if top_trigger else [],
                "components": {
                    "retriever": type(self.retriever).__name__ if self.retriever is not None else "_StubRetriever",
                    "reranker": type(self.reranker).__name__ if self.reranker is not None else "_PassthroughReranker",
                    "slot_extractor": type(self.slot_extractor).__name__ if self.slot_extractor is not None else "_StubSlotExtractor",
                },
            }
        )
        return payload

    @staticmethod
    def _find_trigger(triggers: List[TriggerDef], trigger_id: str) -> Optional[TriggerDef]:
        for t in triggers:
            if t.trigger_id == trigger_id:
                return t
        return None


@dataclass
class _StubRetriever:
    def retrieve(self, query: str, triggers: List[TriggerDef], top_k: int) -> List[CandidateScore]:
        q = str(query or "").strip().lower()
        out: List[CandidateScore] = []
        for trig in triggers:
            score = 0.02
            text = " ".join([trig.name, trig.description, " ".join(trig.aliases)]).lower()
            if q and any(alias.lower() in q for alias in trig.aliases if alias):
                score += 0.30
            if q and trig.name.lower() in q:
                score += 0.20
            if q and text and any(tok in text for tok in q.split()[:2]):
                score += 0.05
            score = max(0.0, min(1.0, score))
            out.append(
                CandidateScore(
                    trigger_id=trig.trigger_id,
                    name=trig.name,
                    recall_score=score,
                    final_score=score,
                    notes="stub_retriever",
                )
            )
        out.sort(key=lambda c: float(c.final_score or 0.0), reverse=True)
        return out[: max(1, int(top_k))]


@dataclass
class _PassthroughReranker:
    def rerank(
        self,
        query: str,
        candidates: List[CandidateScore],
        triggers_by_id: Dict[str, TriggerDef],
    ) -> List[CandidateScore]:
        out: List[CandidateScore] = []
        for c in candidates:
            score = float(c.final_score if c.final_score is not None else (c.recall_score or 0.0))
            out.append(
                CandidateScore(
                    trigger_id=c.trigger_id,
                    name=c.name or (triggers_by_id.get(c.trigger_id).name if c.trigger_id in triggers_by_id else ""),
                    recall_score=c.recall_score,
                    rerank_score=score,
                    final_score=score,
                    notes=c.notes,
                    reasons=list(c.reasons),
                )
            )
        out.sort(key=lambda c: float(c.final_score or 0.0), reverse=True)
        return out


@dataclass
class _StubSlotExtractor:
    def extract(self, query: str, trigger: TriggerDef) -> Dict[str, Any]:
        # Minimal fallback when dedicated extractor is unavailable.
        return {}


def _normalize_candidates(raw: Any, triggers: List[TriggerDef]) -> List[CandidateScore]:
    by_id = {t.trigger_id: t for t in triggers}
    out: List[CandidateScore] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        out.append(_as_candidate(item, by_id))
    return out


def _as_candidate(item: Any, by_id: Dict[str, TriggerDef]) -> CandidateScore:
    if isinstance(item, CandidateScore):
        if item.final_score is None:
            fallback = item.rerank_score if item.rerank_score is not None else (item.recall_score or 0.0)
            return CandidateScore(
                trigger_id=item.trigger_id,
                name=item.name,
                recall_score=item.recall_score,
                rerank_score=item.rerank_score,
                final_score=float(fallback),
                notes=item.notes,
                reasons=list(item.reasons),
            )
        return item

    if isinstance(item, dict):
        trigger_id = str(item.get("trigger_id") or "").strip()
        name = str(item.get("name") or (by_id.get(trigger_id).name if trigger_id in by_id else "")).strip()
        recall = _as_optional_float(item.get("recall_score"))
        rerank = _as_optional_float(item.get("rerank_score"))
        final = _as_optional_float(item.get("final_score"))
        if final is None:
            final = _as_optional_float(item.get("combined_score"))
        if final is None:
            final = rerank if rerank is not None else (recall if recall is not None else 0.0)
        return CandidateScore(
            trigger_id=trigger_id,
            name=name,
            recall_score=recall,
            rerank_score=rerank,
            final_score=final,
            notes=str(item.get("notes")) if item.get("notes") is not None else None,
            reasons=[str(x) for x in (item.get("reasons") or [])],
        )

    trigger_id = str(getattr(item, "trigger_id", "")).strip()
    name = str(getattr(item, "name", "")).strip()
    recall = _as_optional_float(getattr(item, "recall_score", None))
    rerank = _as_optional_float(getattr(item, "rerank_score", None))
    final = _as_optional_float(getattr(item, "final_score", None))
    if final is None:
        final = _as_optional_float(getattr(item, "combined_score", None))
    if final is None:
        final = rerank if rerank is not None else (recall if recall is not None else 0.0)
    return CandidateScore(
        trigger_id=trigger_id,
        name=name,
        recall_score=recall,
        rerank_score=rerank,
        final_score=final,
        notes=str(getattr(item, "notes", "")) or None,
        reasons=[str(x) for x in (getattr(item, "reasons", []) or [])],
    )


def _as_optional_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _trigger_to_dict(trigger: TriggerDef) -> Dict[str, Any]:
    return {
        "trigger_id": trigger.trigger_id,
        "name": trigger.name,
        "description": trigger.description,
        "aliases": list(trigger.aliases),
        "positive_examples": list(trigger.positive_examples),
        "negative_examples": list(trigger.negative_examples),
        "required_slots": [dict(x) if isinstance(x, dict) else {"slot_name": str(getattr(x, "slot_name", ""))} for x in trigger.required_slots],
        "optional_slots": [dict(x) if isinstance(x, dict) else {"slot_name": str(getattr(x, "slot_name", ""))} for x in trigger.optional_slots],
        "enabled": bool(trigger.enabled),
        "tags": list(trigger.tags),
    }

