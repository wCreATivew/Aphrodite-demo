from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

DEFAULT_LEDGER_PATH = "outputs/error_ledger.jsonl"
DEFAULT_EVAL_LEDGER_PATH = "outputs/eval/error_ledger.jsonl"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_ledger_record(
    *,
    query: Any = None,
    predicted_decision: Any = None,
    predicted_trigger: Any = None,
    expected_decision: Any = None,
    expected_trigger: Any = None,
    top_k_candidates: Any = None,
    recall_scores: Any = None,
    rerank_scores: Any = None,
    margin: Any = None,
    extracted_slots: Any = None,
    missing_slots: Any = None,
    clarification_question: Any = None,
    reasons: Any = None,
    config_version: Any = None,
    policy_version: Any = None,
    dataset_version: Any = None,
    timestamp: Any = None,
    run_id: Any = None,
    note: Any = None,
    source: Any = None,
) -> Dict[str, Any]:
    return {
        "query": _to_opt_str(query),
        "predicted_decision": _to_opt_str(predicted_decision),
        "predicted_trigger": _to_opt_str(predicted_trigger),
        "expected_decision": _to_opt_str(expected_decision),
        "expected_trigger": _to_opt_str(expected_trigger),
        "top_k_candidates": _to_str_list(top_k_candidates),
        "recall_scores": _to_scores(recall_scores),
        "rerank_scores": _to_scores(rerank_scores),
        "margin": _to_opt_float(margin),
        "extracted_slots": _to_dict(extracted_slots),
        "missing_slots": _to_str_list(missing_slots),
        "clarification_question": _to_opt_str(clarification_question),
        "reasons": _to_str_list(reasons),
        "config_version": _to_opt_str(config_version),
        "policy_version": _to_opt_str(policy_version),
        "dataset_version": _to_opt_str(dataset_version),
        "timestamp": _to_opt_str(timestamp) or now_utc_iso(),
        "run_id": _to_opt_str(run_id),
        "note": _to_opt_str(note),
        "source": _to_opt_str(source),
    }


def make_ledger_record_from_prediction(
    prediction: Any,
    *,
    query: Any = None,
    expected_decision: Any = None,
    expected_trigger: Any = None,
    run_id: Any = None,
    note: Any = None,
    source: Any = "engine_result",
) -> Dict[str, Any]:
    data = _as_mapping(prediction)
    debug = _as_mapping(data.get("debug") or data.get("debug_trace"))
    cands = data.get("candidates") or []

    top_k = _to_str_list(data.get("top_k_candidates") or debug.get("top_k_candidates"))
    if not top_k and isinstance(cands, list):
        top_k = [str(_as_mapping(c).get("trigger_id") or "") for c in cands if str(_as_mapping(c).get("trigger_id") or "").strip()]

    recall = data.get("recall_scores") or debug.get("recall_scores")
    if not recall and isinstance(cands, list):
        recall = {str(_as_mapping(c).get("trigger_id") or ""): _as_mapping(c).get("recall_score") for c in cands if str(_as_mapping(c).get("trigger_id") or "").strip()}

    rerank = data.get("rerank_scores") or debug.get("rerank_scores")
    if not rerank and isinstance(cands, list):
        rerank = {str(_as_mapping(c).get("trigger_id") or ""): _as_mapping(c).get("rerank_score") for c in cands if str(_as_mapping(c).get("trigger_id") or "").strip()}

    margin = data.get("margin")
    if margin is None:
        margin = debug.get("margin")

    return make_ledger_record(
        query=query if query is not None else data.get("user_query") or data.get("query"),
        predicted_decision=data.get("decision"),
        predicted_trigger=data.get("selected_trigger"),
        expected_decision=expected_decision,
        expected_trigger=expected_trigger,
        top_k_candidates=top_k,
        recall_scores=recall,
        rerank_scores=rerank,
        margin=margin,
        extracted_slots=data.get("extracted_slots"),
        missing_slots=data.get("missing_slots"),
        clarification_question=data.get("clarification_question"),
        reasons=data.get("reasons"),
        config_version=data.get("config_version") or debug.get("config_version"),
        policy_version=data.get("policy_version") or debug.get("policy_version"),
        dataset_version=data.get("dataset_version") or debug.get("dataset_version"),
        timestamp=data.get("timestamp") or debug.get("timestamp"),
        run_id=run_id if run_id is not None else data.get("run_id") or debug.get("run_id"),
        note=note,
        source=source,
    )


def make_ledger_record_from_eval_sample(
    sample: Any,
    *,
    run_id: Any = None,
    note: Any = None,
    source: Any = "eval_sample",
) -> Dict[str, Any]:
    row = _as_mapping(sample)
    return make_ledger_record(
        query=row.get("query"),
        predicted_decision=row.get("predicted_decision"),
        predicted_trigger=row.get("predicted_trigger"),
        expected_decision=row.get("expected_decision"),
        expected_trigger=row.get("expected_trigger"),
        top_k_candidates=row.get("top_k_candidates"),
        recall_scores=row.get("recall_scores"),
        rerank_scores=row.get("rerank_scores"),
        margin=row.get("margin"),
        extracted_slots=row.get("extracted_slots"),
        missing_slots=row.get("missing_slots"),
        clarification_question=row.get("clarification_question"),
        reasons=row.get("reasons"),
        config_version=row.get("config_version"),
        policy_version=row.get("policy_version"),
        dataset_version=row.get("dataset_version"),
        timestamp=row.get("timestamp"),
        run_id=run_id if run_id is not None else row.get("run_id"),
        note=note,
        source=source,
    )


def append_ledger_record(path: str | Path, record: Mapping[str, Any]) -> int:
    return append_many_records(path, [record])


def append_many_records(path: str | Path, records: Iterable[Mapping[str, Any]]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with p.open("a", encoding="utf-8") as f:
        for raw in records:
            rec = make_ledger_record_from_eval_sample(raw, source=_as_mapping(raw).get("source"))
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count


def classify_error_type(
    *,
    predicted_decision: Any,
    predicted_trigger: Any,
    expected_decision: Any,
    expected_trigger: Any,
) -> str:
    pred_d = str(predicted_decision or "")
    exp_d = str(expected_decision or "")
    pred_t = str(predicted_trigger or "")
    exp_t = str(expected_trigger or "")
    if not exp_d:
        return "unlabeled"
    if pred_d == exp_d and (exp_d != "trigger" or pred_t == exp_t):
        return "match"
    if exp_d == "no_trigger" and pred_d == "trigger":
        return "false_positive"
    if exp_d == "trigger" and pred_d == "no_trigger":
        return "false_negative"
    if exp_d == "trigger" and pred_d == "ask_clarification":
        return "clarify_mismatch"
    if exp_d == "ask_clarification" and pred_d != "ask_clarification":
        return "clarify_mismatch"
    if exp_d == "trigger" and pred_d == "trigger" and exp_t and pred_t and exp_t != pred_t:
        return "wrong_trigger"
    return "decision_mismatch"


def build_ledger_entry(**kwargs: Any) -> Dict[str, Any]:
    rec = make_ledger_record(**kwargs)
    rec["error_type"] = classify_error_type(
        predicted_decision=rec.get("predicted_decision"),
        predicted_trigger=rec.get("predicted_trigger"),
        expected_decision=rec.get("expected_decision"),
        expected_trigger=rec.get("expected_trigger"),
    )
    return rec


def build_ledger_row(
    *,
    query: str,
    result: Any,
    expected_decision: str = "",
    expected_trigger: str = "",
) -> Dict[str, Any]:
    rec = make_ledger_record_from_prediction(
        result,
        query=query,
        expected_decision=expected_decision,
        expected_trigger=expected_trigger,
        source="engine_result",
    )
    rec["error_type"] = classify_error_type(
        predicted_decision=rec.get("predicted_decision"),
        predicted_trigger=rec.get("predicted_trigger"),
        expected_decision=rec.get("expected_decision"),
        expected_trigger=rec.get("expected_trigger"),
    )
    return rec


def build_hard_negatives_from_ledger(rows: Iterable[Dict[str, Any]], *, min_margin: float = 0.0) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        et = str(row.get("error_type") or classify_error_type(
            predicted_decision=row.get("predicted_decision"),
            predicted_trigger=row.get("predicted_trigger"),
            expected_decision=row.get("expected_decision"),
            expected_trigger=row.get("expected_trigger"),
        ))
        if et not in {"false_positive", "wrong_trigger"}:
            continue
        margin = _to_opt_float(row.get("margin"))
        if margin is not None and margin < float(min_margin):
            continue
        q = _to_opt_str(row.get("query"))
        t = _to_opt_str(row.get("predicted_trigger"))
        if not q or not t:
            continue
        out.append({"query": q, "confusable_with": t, "source": "error_ledger", "timestamp": _to_opt_str(row.get("timestamp")) or now_utc_iso()})
    return out


def to_hard_negative(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    et = str(entry.get("error_type") or "")
    if et not in {"false_positive", "wrong_trigger"}:
        return None
    query = _to_opt_str(entry.get("query"))
    trigger = _to_opt_str(entry.get("predicted_trigger"))
    if not query or not trigger:
        return None
    return {
        "query": query,
        "confusable_with": trigger,
        "source": "error_ledger",
        "timestamp": _to_opt_str(entry.get("timestamp")) or now_utc_iso(),
    }


def summarize_ledger(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    by_type: Dict[str, int] = {}
    for row in rows:
        total += 1
        et = str(row.get("error_type") or classify_error_type(
            predicted_decision=row.get("predicted_decision"),
            predicted_trigger=row.get("predicted_trigger"),
            expected_decision=row.get("expected_decision"),
            expected_trigger=row.get("expected_trigger"),
        ))
        by_type[et] = int(by_type.get(et, 0)) + 1
    return {"total": total, "error_count": max(0, total - by_type.get("match", 0) - by_type.get("unlabeled", 0)), "error_type_breakdown": by_type}


def append_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> int:
    return append_many_records(path, rows)


def append_jsonl_unique(path: str | Path, rows: Iterable[Dict[str, Any]], *, dedupe_key: str = "query") -> int:
    p = Path(path)
    merged: Dict[str, Dict[str, Any]] = {}
    if p.exists():
        with p.open("r", encoding="utf-8-sig") as f:
            for raw in f:
                line = str(raw or "").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                key = str(obj.get(dedupe_key) or "").strip()
                if key:
                    merged[key] = obj
    for row in rows:
        rec = make_ledger_record_from_eval_sample(row, source=_as_mapping(row).get("source"))
        key = str(rec.get(dedupe_key) or "").strip()
        if key:
            merged[key] = rec
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for rec in merged.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(merged)


def _as_mapping(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if is_dataclass(obj):
        try:
            return dict(asdict(obj))
        except Exception:
            return {}
    if hasattr(obj, "model_dump"):
        try:
            out = obj.model_dump()
            if isinstance(out, dict):
                return dict(out)
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return dict(vars(obj))
        except Exception:
            return {}
    return {}


def _to_opt_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    text = str(v).strip()
    return text or None


def _to_opt_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _to_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return dict(v)
    return {}


def _to_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, (list, tuple, set)):
        return [str(x) for x in v if str(x).strip()]
    return [str(v)]


def _to_scores(v: Any) -> Dict[str, Optional[float]]:
    if isinstance(v, dict):
        return {str(k): _to_opt_float(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return {str(i): _to_opt_float(val) for i, val in enumerate(v, start=1)}
    return {}
