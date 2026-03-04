from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


def build_eval_report(
    rows: List[Dict[str, Any]],
    *,
    config_version: str = "v1",
    policy_version: str = "v1",
    dataset_version: str = "unknown",
) -> Dict[str, Any]:
    total = len(rows)
    if total <= 0:
        return {
            "total": 0,
            "decision_accuracy": 0.0,
            "trigger_match_count": 0,
            "trigger_match_rate": 0.0,
            "decision_breakdown": {},
            "error_breakdown": {},
            "by_difficulty": {},
            "by_expected_decision": {},
            "by_predicted_decision": {},
            "false_positives": [],
            "false_negatives": [],
            "error_ledger": [],
            "config_version": str(config_version),
            "policy_version": str(policy_version),
            "dataset_version": str(dataset_version),
            "timestamp": _now_iso(),
        }

    decision_hit = 0
    trigger_expect = 0
    trigger_match = 0
    false_pos: List[Dict[str, Any]] = []
    false_neg: List[Dict[str, Any]] = []
    decision_counter: Counter[str] = Counter()
    expected_decision_counter: Counter[str] = Counter()
    error_counter: Counter[str] = Counter()

    for row in rows:
        exp_decision = str(row.get("expected_decision") or "")
        pred_decision = str(row.get("predicted_decision") or "")
        exp_trigger = str(row.get("expected_trigger") or "")
        pred_trigger = str(row.get("predicted_trigger") or "")
        decision_counter[pred_decision] += 1
        expected_decision_counter[exp_decision] += 1

        if exp_decision and pred_decision == exp_decision:
            decision_hit += 1
        if exp_trigger:
            trigger_expect += 1
            if pred_trigger == exp_trigger:
                trigger_match += 1

        pred_is_trigger = pred_decision == "trigger" and bool(pred_trigger)
        exp_is_trigger = exp_decision == "trigger" and bool(exp_trigger)
        if pred_is_trigger and not exp_is_trigger:
            error_counter["false_positive_trigger"] += 1
            false_pos.append(_compact_error_row(row))
        if exp_is_trigger and (not pred_is_trigger or pred_trigger != exp_trigger):
            error_counter["false_negative_trigger"] += 1
            false_neg.append(_compact_error_row(row))
        if exp_is_trigger and pred_is_trigger and pred_trigger != exp_trigger:
            error_counter["wrong_trigger"] += 1
        if exp_decision and pred_decision and exp_decision != pred_decision:
            error_counter["wrong_decision"] += 1
        if exp_decision == "ask_clarification" and pred_decision != "ask_clarification":
            error_counter["clarification_miss"] += 1
        if exp_decision != "ask_clarification" and pred_decision == "ask_clarification":
            error_counter["clarification_overfire"] += 1

    by_difficulty = _group_accuracy(rows, key="difficulty")
    error_ledger = build_error_ledger(
        rows,
        config_version=str(config_version),
        policy_version=str(policy_version),
        dataset_version=str(dataset_version),
    )

    return {
        "total": total,
        "decision_accuracy": round(decision_hit / total, 4),
        "trigger_match_count": trigger_match,
        "trigger_match_rate": round(trigger_match / max(1, trigger_expect), 4),
        "decision_breakdown": dict(decision_counter),
        "error_breakdown": dict(error_counter),
        "by_difficulty": by_difficulty,
        "by_expected_decision": dict(expected_decision_counter),
        "by_predicted_decision": dict(decision_counter),
        "false_positives": false_pos[:20],
        "false_negatives": false_neg[:20],
        "error_buckets": {
            "false_positive": int(error_counter.get("false_positive_trigger", 0)),
            "false_negative": int(error_counter.get("false_negative_trigger", 0)),
            "wrong_trigger": int(error_counter.get("wrong_trigger", 0)),
            "wrong_decision": int(error_counter.get("wrong_decision", 0)),
            "clarification_miss": int(error_counter.get("clarification_miss", 0)),
            "clarification_overfire": int(error_counter.get("clarification_overfire", 0)),
        },
        "error_ledger": error_ledger,
        "config_version": str(config_version),
        "policy_version": str(policy_version),
        "dataset_version": str(dataset_version),
        "timestamp": _now_iso(),
    }


def build_error_ledger(
    traces: Iterable[Dict[str, Any]],
    *,
    config_version: str = "v1",
    policy_version: str = "v1",
    dataset_version: str = "unknown",
) -> List[Dict[str, Any]]:
    ts = _now_iso()
    ledger: List[Dict[str, Any]] = []
    for t in traces:
        debug = dict(t.get("debug_trace") or t.get("debug") or {})
        candidates = list(t.get("candidates") or [])
        top_k_candidates = list(t.get("top_k_candidates") or []) or [str(c.get("trigger_id") or "") for c in candidates if c.get("trigger_id")]
        recall_scores = dict(t.get("recall_scores") or {}) or {
            str(c.get("trigger_id")): c.get("recall_score") for c in candidates if c.get("trigger_id")
        }
        rerank_scores = dict(t.get("rerank_scores") or {}) or {
            str(c.get("trigger_id")): c.get("rerank_score") for c in candidates if c.get("trigger_id")
        }
        row = {
            "query": t.get("query"),
            "predicted_decision": t.get("predicted_decision"),
            "predicted_trigger": t.get("predicted_trigger"),
            "expected_decision": t.get("expected_decision"),
            "expected_trigger": t.get("expected_trigger"),
            "top_k_candidates": top_k_candidates,
            "recall_scores": recall_scores,
            "rerank_scores": rerank_scores,
            "margin": t.get("margin") if t.get("margin") is not None else debug.get("margin"),
            "extracted_slots": t.get("extracted_slots") or {},
            "missing_slots": t.get("missing_slots") or [],
            "clarification_question": t.get("clarification_question"),
            "reasons": t.get("reasons") or [],
            "config_version": str(t.get("config_version") or debug.get("config_version") or config_version),
            "policy_version": str(t.get("policy_version") or debug.get("policy_version") or policy_version),
            "dataset_version": str(t.get("dataset_version") or debug.get("dataset_version") or dataset_version),
            "timestamp": str(t.get("timestamp") or ts),
        }
        ledger.append(row)
    return ledger


def mine_hard_negatives(ledger_rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in ledger_rows:
        exp_decision = str(row.get("expected_decision") or "")
        pred_decision = str(row.get("predicted_decision") or "")
        pred_trigger = str(row.get("predicted_trigger") or "")
        query = str(row.get("query") or "").strip()
        if not query:
            continue
        if exp_decision in {"no_trigger", "ask_clarification"} and pred_decision == "trigger" and pred_trigger:
            key = (query, pred_trigger)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "query": query,
                    "confusable_with": pred_trigger,
                    "source": "error_ledger_fp",
                    "timestamp": row.get("timestamp"),
                }
            )
    return out


def _group_accuracy(rows: List[Dict[str, Any]], *, key: str) -> Dict[str, Dict[str, float]]:
    bucket: Dict[str, Dict[str, float]] = {}
    for row in rows:
        group = str(row.get(key) or "unknown").strip() or "unknown"
        item = bucket.setdefault(group, {"total": 0.0, "decision_hit": 0.0, "trigger_hit": 0.0, "trigger_total": 0.0})
        item["total"] += 1
        exp_decision = str(row.get("expected_decision") or "")
        pred_decision = str(row.get("predicted_decision") or "")
        exp_trigger = str(row.get("expected_trigger") or "")
        pred_trigger = str(row.get("predicted_trigger") or "")
        if exp_decision and pred_decision == exp_decision:
            item["decision_hit"] += 1
        if exp_trigger:
            item["trigger_total"] += 1
            if pred_trigger == exp_trigger:
                item["trigger_hit"] += 1
    for v in bucket.values():
        total = max(1.0, float(v["total"]))
        trig_total = max(1.0, float(v["trigger_total"]))
        v["decision_accuracy"] = round(float(v["decision_hit"]) / total, 4)
        v["trigger_match_rate"] = round(float(v["trigger_hit"]) / trig_total, 4)
    return bucket


def _compact_error_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "query": row.get("query"),
        "expected_decision": row.get("expected_decision"),
        "expected_trigger": row.get("expected_trigger"),
        "predicted_decision": row.get("predicted_decision"),
        "predicted_trigger": row.get("predicted_trigger"),
        "margin": row.get("margin"),
        "top_k_candidates": row.get("top_k_candidates"),
        "reasons": row.get("reasons"),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
