from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping

try:
    from .text_normalize import normalize_text, token_counts
except ImportError:
    from text_normalize import normalize_text, token_counts  # type: ignore


def compute_idf(doc_tfs: Iterable[Dict[str, int]]) -> Dict[str, float]:
    docs = list(doc_tfs)
    if not docs:
        return {}
    doc_n = float(len(docs))
    df: Dict[str, int] = {}
    for tf in docs:
        for token in tf.keys():
            df[token] = df.get(token, 0) + 1
    out: Dict[str, float] = {}
    for token, freq in df.items():
        out[token] = 1.0 + math.log((1.0 + doc_n) / (1.0 + float(freq)))
    return out


def weighted_jaccard(q_tf: Dict[str, int], d_tf: Dict[str, int], idf: Dict[str, float]) -> float:
    if not q_tf or not d_tf:
        return 0.0
    keys = set(q_tf.keys()) | set(d_tf.keys())
    num = 0.0
    den = 0.0
    for key in keys:
        weight = float(idf.get(key, 1.0))
        qv = float(q_tf.get(key, 0))
        dv = float(d_tf.get(key, 0))
        num += min(qv, dv) * weight
        den += max(qv, dv) * weight
    if den <= 0.0:
        return 0.0
    return float(num / den)


def tfidf_cosine(q_tf: Dict[str, int], d_tf: Dict[str, int], idf: Dict[str, float]) -> float:
    if not q_tf or not d_tf:
        return 0.0
    keys = set(q_tf.keys()) | set(d_tf.keys())
    dot = 0.0
    q_norm = 0.0
    d_norm = 0.0
    for key in keys:
        weight = float(idf.get(key, 1.0))
        qv = float(q_tf.get(key, 0)) * weight
        dv = float(d_tf.get(key, 0)) * weight
        dot += qv * dv
        q_norm += qv * qv
        d_norm += dv * dv
    if q_norm <= 0.0 or d_norm <= 0.0:
        return 0.0
    return float(dot / math.sqrt(q_norm * d_norm))


def clamp01(value: float) -> float:
    return float(max(0.0, min(1.0, float(value))))


def max_text_similarity(query_tf: Dict[str, int], texts: Iterable[str], idf: Dict[str, float]) -> float:
    best = 0.0
    for text in texts:
        score = tfidf_cosine(query_tf, token_counts(text), idf)
        if score > best:
            best = score
    return best


def coerce_trigger(trigger: Any) -> Dict[str, Any]:
    if isinstance(trigger, Mapping):
        getter = trigger.get
    else:
        getter = lambda k, default=None: getattr(trigger, k, default)

    aliases = [str(x) for x in (getter("aliases", []) or [])]
    positive_examples = [str(x) for x in (getter("positive_examples", []) or [])]
    negative_examples = [str(x) for x in (getter("negative_examples", []) or [])]

    required_slots = getter("required_slots", []) or []
    optional_slots = getter("optional_slots", []) or []

    return {
        "trigger_id": str(getter("trigger_id", "") or "").strip(),
        "name": str(getter("name", "") or "").strip(),
        "description": str(getter("description", "") or "").strip(),
        "aliases": aliases,
        "positive_examples": positive_examples,
        "negative_examples": negative_examples,
        "required_slots": list(required_slots),
        "optional_slots": list(optional_slots),
        "enabled": bool(getter("enabled", True)),
        "tags": [str(x) for x in (getter("tags", []) or [])],
    }


def trigger_searchable_text(trigger: Mapping[str, Any]) -> str:
    parts = [
        str(trigger.get("name") or ""),
        str(trigger.get("description") or ""),
        " ".join(str(x) for x in (trigger.get("aliases") or [])),
        " ".join(str(x) for x in (trigger.get("positive_examples") or [])),
        " ".join(str(x) for x in (trigger.get("negative_examples") or [])),
    ]
    return "\n".join(x for x in parts if x).strip()


def build_trigger_map(triggers: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in triggers:
        trig = coerce_trigger(item)
        tid = str(trig.get("trigger_id") or "").strip()
        if not tid:
            continue
        out[tid] = trig
    return out


def candidate_to_dict(candidate: Any) -> Dict[str, Any]:
    if isinstance(candidate, Mapping):
        getter = candidate.get
    else:
        getter = lambda k, default=None: getattr(candidate, k, default)
    return {
        "trigger_id": str(getter("trigger_id", "") or "").strip(),
        "recall_score": _to_opt_float(getter("recall_score")),
        "rerank_score": _to_opt_float(getter("rerank_score")),
        "final_score": _to_opt_float(getter("final_score")),
        "notes": _to_opt_str(getter("notes")),
    }


def candidates_to_dicts(candidates: Iterable[Any]) -> List[Dict[str, Any]]:
    return [candidate_to_dict(x) for x in candidates]


def _to_opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
