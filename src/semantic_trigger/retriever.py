from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

try:
    from .schemas import CandidateScore
    from .scoring_utils import (
        candidates_to_dicts,
        clamp01,
        coerce_trigger,
        compute_idf,
        max_text_similarity,
        normalize_text,
        token_counts,
        trigger_searchable_text,
    )
except ImportError:
    from schemas import CandidateScore  # type: ignore
    from scoring_utils import (  # type: ignore
        candidates_to_dicts,
        clamp01,
        coerce_trigger,
        compute_idf,
        max_text_similarity,
        normalize_text,
        token_counts,
        trigger_searchable_text,
    )

# Baseline action hints used by recall stage.
_ACTION_HINTS = {
    "set_reminder": ["提醒", "remind", "reminder", "闹钟", "alarm"],
    "send_message": ["发", "消息", "message", "text", "邮件", "email"],
    "weather_query": ["天气", "weather", "forecast", "温度", "下雨"],
    "translate_text": ["翻译", "translate", "译成", "译为"],
    "summarize_text": ["总结", "摘要", "summarize", "summary"],
    "open_file": ["打开", "open", "文件", "file"],
    "code_debug": ["debug", "调试", "报错", "异常", "traceback", "bug", "崩溃", "修复", "修bug"],
}


def retrieve_candidates(query: str, triggers: Iterable[Any], top_k: int = 10) -> List[CandidateScore]:
    """Baseline lexical recall.

    Args:
        query: user query text.
        triggers: iterable of TriggerDef-like or dict-like objects.
        top_k: max candidates to return.

    Returns:
        Candidates sorted by recall_score desc.
    """
    q = str(query or "").strip()
    if not q:
        return []

    normalized_triggers = [coerce_trigger(t) for t in triggers]
    enabled_triggers = [t for t in normalized_triggers if bool(t.get("enabled", True)) and t.get("trigger_id")]
    if not enabled_triggers:
        return []

    q_tf = token_counts(q)
    q_norm = normalize_text(q)
    doc_tfs = [token_counts(trigger_searchable_text(t)) for t in enabled_triggers]
    idf = compute_idf(doc_tfs + [q_tf])

    scored: List[CandidateScore] = []
    for trig in enabled_triggers:
        trigger_id = str(trig.get("trigger_id") or "")
        name = str(trig.get("name") or trigger_id)

        name_desc = f"{trig.get('name', '')} {trig.get('description', '')}".strip()
        desc_score = max_text_similarity(q_tf, [name_desc], idf)
        alias_score = max_text_similarity(q_tf, trig.get("aliases", []), idf)
        pos_score = max_text_similarity(q_tf, trig.get("positive_examples", [])[:20], idf)
        neg_score = max_text_similarity(q_tf, trig.get("negative_examples", [])[:20], idf)

        alias_exact = 1.0 if _alias_exact_hit(q_norm, trig.get("aliases", [])) else 0.0
        action_score = _action_hint_score(q_norm, trig)

        recall = (
            0.24 * desc_score
            + 0.24 * alias_score
            + 0.34 * pos_score
            + 0.12 * alias_exact
            + 0.10 * action_score
            - 0.22 * neg_score
        )
        recall = clamp01(recall)

        reasons = [
            f"recall_desc={desc_score:.4f}",
            f"recall_alias={alias_score:.4f}",
            f"recall_pos={pos_score:.4f}",
            f"recall_neg={neg_score:.4f}",
            f"recall_alias_exact={alias_exact:.4f}",
            f"recall_action={action_score:.4f}",
        ]
        notes = (
            f"stage=recall; desc={desc_score:.3f}; alias={alias_score:.3f}; "
            f"pos={pos_score:.3f}; neg={neg_score:.3f}; action={action_score:.3f}"
        )
        scored.append(
            CandidateScore(
                trigger_id=trigger_id,
                name=name,
                recall_score=recall,
                rerank_score=None,
                final_score=recall,
                notes=notes,
                reasons=reasons,
            )
        )

    scored.sort(key=lambda x: float(x.recall_score or 0.0), reverse=True)
    return scored[: max(1, int(top_k))]


def retrieve_candidates_dict(query: str, triggers: Iterable[Any], top_k: int = 10) -> List[dict[str, Any]]:
    """Dict-output adapter for strict protocol consumers."""
    rows = retrieve_candidates(query=query, triggers=triggers, top_k=top_k)
    return candidates_to_dicts(rows)


@dataclass
class CandidateRetriever:
    # Keep compatibility with existing engine builder signature.
    embedder: object | None = None

    def recall(self, query: str, triggers: List[Any], top_k: int = 20) -> List[CandidateScore]:
        return retrieve_candidates(query=query, triggers=triggers, top_k=top_k)


def _alias_exact_hit(query_norm: str, aliases: Iterable[str]) -> bool:
    if not query_norm:
        return False
    for alias in aliases:
        token = normalize_text(alias)
        if token and token in query_norm:
            return True
    return False


def _action_hint_score(query_norm: str, trigger: dict[str, Any]) -> float:
    trigger_id = str(trigger.get("trigger_id") or "").strip().lower()
    trigger_text = normalize_text(
        " ".join(
            [
                str(trigger.get("name") or ""),
                str(trigger.get("description") or ""),
                " ".join(trigger.get("aliases") or []),
            ]
        )
    )

    hints = list(_ACTION_HINTS.get(trigger_id, []))
    if not hints:
        # fallback: infer hints from trigger text
        hints = [x for x in ["提醒", "消息", "翻译", "总结", "天气", "文件", "remind", "message", "translate", "summary", "weather", "file"] if x in trigger_text]
    if not hints:
        return 0.0

    hit = 0
    for hint in hints:
        marker = normalize_text(hint)
        if marker and marker in query_norm:
            hit += 1
    return clamp01(hit / max(1, min(4, len(hints))))
