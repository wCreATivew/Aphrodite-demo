from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class EvalRow:
    query: str
    expected_decision: str
    expected_trigger: str
    predicted_decision: str
    predicted_trigger: str
    difficulty: str = "unknown"
    split: str = "main"
    error_type: str = ""


def compute_overall_metrics(rows: Iterable[EvalRow]) -> Dict[str, float]:
    rs = list(rows)
    tp = fp = fn = 0
    for r in rs:
        pred_pos = (r.predicted_decision == "trigger") and bool(r.predicted_trigger)
        gold_pos = (r.expected_decision == "trigger") and bool(r.expected_trigger)
        hit = pred_pos and gold_pos and (r.predicted_trigger == r.expected_trigger)
        if hit:
            tp += 1
        elif pred_pos and not hit:
            fp += 1
        elif gold_pos and not hit:
            fn += 1
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "decision_accuracy": float(_decision_accuracy(rs)),
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
        "total": float(len(rs)),
    }


def compute_trigger_level_metrics(rows: Iterable[EvalRow]) -> Dict[str, Dict[str, float]]:
    rs = list(rows)
    all_ids = sorted(set([r.expected_trigger for r in rs if r.expected_trigger] + [r.predicted_trigger for r in rs if r.predicted_trigger]))
    out: Dict[str, Dict[str, float]] = {}
    for tid in all_ids:
        tp = fp = fn = 0
        for r in rs:
            pred = r.predicted_trigger == tid and r.predicted_decision == "trigger"
            gold = r.expected_trigger == tid and r.expected_decision == "trigger"
            if pred and gold:
                tp += 1
            elif pred and not gold:
                fp += 1
            elif gold and not pred:
                fn += 1
        p = tp / max(1, tp + fp)
        rc = tp / max(1, tp + fn)
        f1 = 2 * p * rc / max(1e-9, p + rc)
        out[tid] = {"precision": p, "recall": rc, "f1": f1, "tp": float(tp), "fp": float(fp), "fn": float(fn)}
    return out


def confusion_pairs(rows: Iterable[EvalRow], top_n: int = 20) -> List[Tuple[str, int]]:
    c = Counter()
    for r in rows:
        if r.expected_trigger and r.predicted_trigger and r.expected_trigger != r.predicted_trigger:
            c[(r.expected_trigger, r.predicted_trigger)] += 1
    pairs = c.most_common(max(1, int(top_n)))
    return [(f"{a}->{b}", n) for (a, b), n in pairs]


def false_cases(rows: Iterable[EvalRow], limit: int = 30) -> Dict[str, List[Dict[str, str]]]:
    fp_cases: List[Dict[str, str]] = []
    fn_cases: List[Dict[str, str]] = []
    for r in rows:
        pred_hit = (r.predicted_decision == "trigger") and bool(r.predicted_trigger)
        gold_hit = (r.expected_decision == "trigger") and bool(r.expected_trigger)
        if pred_hit and (r.predicted_trigger != r.expected_trigger):
            fp_cases.append({"query": r.query, "expected": r.expected_trigger, "predicted": r.predicted_trigger})
        if gold_hit and (r.predicted_trigger != r.expected_trigger):
            fn_cases.append({"query": r.query, "expected": r.expected_trigger, "predicted": r.predicted_trigger})
    return {"false_positive": fp_cases[:limit], "false_negative": fn_cases[:limit]}


def compute_decision_level_metrics(rows: Iterable[EvalRow]) -> Dict[str, Dict[str, float]]:
    rs = list(rows)
    labels = ["trigger", "no_trigger", "ask_clarification"]
    out: Dict[str, Dict[str, float]] = {}
    for label in labels:
        tp = fp = fn = 0
        for r in rs:
            pred = r.predicted_decision == label
            gold = r.expected_decision == label
            if pred and gold:
                tp += 1
            elif pred and not gold:
                fp += 1
            elif gold and not pred:
                fn += 1
        p = tp / max(1, tp + fp)
        rc = tp / max(1, tp + fn)
        f1 = 2 * p * rc / max(1e-9, p + rc)
        out[label] = {
            "precision": float(p),
            "recall": float(rc),
            "f1": float(f1),
            "tp": float(tp),
            "fp": float(fp),
            "fn": float(fn),
        }
    return out


def compute_difficulty_metrics(rows: Iterable[EvalRow]) -> Dict[str, Dict[str, float]]:
    groups: Dict[str, List[EvalRow]] = defaultdict(list)
    for r in rows:
        groups[str(r.difficulty or "unknown")].append(r)
    out: Dict[str, Dict[str, float]] = {}
    for key, vals in groups.items():
        stats = compute_overall_metrics(vals)
        out[key] = {
            "precision": float(stats["precision"]),
            "recall": float(stats["recall"]),
            "f1": float(stats["f1"]),
            "decision_accuracy": float(stats["decision_accuracy"]),
            "total": float(stats["total"]),
        }
    return out


def compute_error_type_breakdown(rows: Iterable[EvalRow]) -> Dict[str, int]:
    counter: Dict[str, int] = {}
    for r in rows:
        et = str(r.error_type or _infer_error_type(r))
        counter[et] = int(counter.get(et, 0)) + 1
    return counter


def _decision_accuracy(rows: List[EvalRow]) -> float:
    if not rows:
        return 0.0
    hit = 0
    for r in rows:
        if str(r.expected_decision or "") == str(r.predicted_decision or ""):
            hit += 1
    return hit / max(1, len(rows))


def _infer_error_type(row: EvalRow) -> str:
    if row.expected_decision == row.predicted_decision and (
        row.expected_decision != "trigger" or row.expected_trigger == row.predicted_trigger
    ):
        return "match"
    if row.expected_decision == "no_trigger" and row.predicted_decision == "trigger":
        return "false_positive"
    if row.expected_decision == "trigger" and row.predicted_decision == "no_trigger":
        return "false_negative"
    if row.expected_decision == "trigger" and row.predicted_decision == "trigger" and row.expected_trigger != row.predicted_trigger:
        return "wrong_trigger"
    if row.expected_decision == "trigger" and row.predicted_decision == "ask_clarification":
        return "clarification_overuse"
    if row.expected_decision == "ask_clarification" and row.predicted_decision == "trigger":
        return "clarification_missed"
    return "decision_mismatch"


def to_eval_rows(rows: Iterable[Dict[str, Any] | EvalRow]) -> List[EvalRow]:
    out: List[EvalRow] = []
    for item in rows:
        if isinstance(item, EvalRow):
            out.append(item)
            continue
        obj = dict(item or {})
        out.append(
            EvalRow(
                query=str(obj.get("query") or ""),
                expected_decision=str(obj.get("expected_decision") or "no_trigger"),
                expected_trigger=str(obj.get("expected_trigger") or ""),
                predicted_decision=str(obj.get("predicted_decision") or "no_trigger"),
                predicted_trigger=str(obj.get("predicted_trigger") or ""),
                difficulty=str(obj.get("difficulty") or "unknown"),
                split=str(obj.get("split") or "main"),
                error_type=str(obj.get("error_type") or ""),
            )
        )
    return out


def decision_classification_metrics(rows: Iterable[Dict[str, Any] | EvalRow]) -> Dict[str, Any]:
    rs = to_eval_rows(rows)
    overall = compute_overall_metrics(rs)
    decision_breakdown = compute_decision_level_metrics(rs)
    return {
        "decision_accuracy": overall["decision_accuracy"],
        "macro_f1": round(
            (
                float(decision_breakdown["trigger"]["f1"])
                + float(decision_breakdown["no_trigger"]["f1"])
                + float(decision_breakdown["ask_clarification"]["f1"])
            )
            / 3.0,
            4,
        ),
        "per_decision": decision_breakdown,
    }


def trigger_match_stats(rows: Iterable[Dict[str, Any] | EvalRow]) -> Dict[str, float]:
    rs = to_eval_rows(rows)
    total_expect = 0
    correct_match = 0
    for r in rs:
        if r.expected_decision == "trigger" and r.expected_trigger:
            total_expect += 1
            if r.predicted_decision == "trigger" and r.predicted_trigger == r.expected_trigger:
                correct_match += 1
    return {
        "trigger_expected_total": float(total_expect),
        "trigger_match_count": float(correct_match),
        "trigger_match_rate": float(correct_match / max(1, total_expect)),
    }


def no_trigger_metrics(rows: Iterable[Dict[str, Any] | EvalRow]) -> Dict[str, float]:
    return _decision_label_metrics(to_eval_rows(rows), label="no_trigger")


def ask_clarification_metrics(rows: Iterable[Dict[str, Any] | EvalRow]) -> Dict[str, float]:
    return _decision_label_metrics(to_eval_rows(rows), label="ask_clarification")


def _decision_label_metrics(rows: List[EvalRow], *, label: str) -> Dict[str, float]:
    tp = fp = fn = 0
    for r in rows:
        pred = r.predicted_decision == label
        gold = r.expected_decision == label
        if pred and gold:
            tp += 1
        elif pred and not gold:
            fp += 1
        elif gold and not pred:
            fn += 1
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
    }
