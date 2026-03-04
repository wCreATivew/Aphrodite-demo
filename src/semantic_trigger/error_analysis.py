from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Tuple


def collect_false_positives(rows: Iterable[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        exp_decision = str(row.get("expected_decision") or "")
        pred_decision = str(row.get("predicted_decision") or "")
        pred_trigger = str(row.get("predicted_trigger") or "")
        if exp_decision != "trigger" and pred_decision == "trigger" and pred_trigger:
            out.append(_compact_row(row))
    return out[: max(1, int(limit))]


def collect_false_negatives(rows: Iterable[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        exp_decision = str(row.get("expected_decision") or "")
        exp_trigger = str(row.get("expected_trigger") or "")
        pred_decision = str(row.get("predicted_decision") or "")
        pred_trigger = str(row.get("predicted_trigger") or "")
        if exp_decision == "trigger" and exp_trigger:
            if pred_decision != "trigger" or pred_trigger != exp_trigger:
                out.append(_compact_row(row))
    return out[: max(1, int(limit))]


def top_confusion_pairs(rows: Iterable[Dict[str, Any]], top_n: int = 20) -> List[Dict[str, Any]]:
    counter: Counter[Tuple[str, str]] = Counter()
    examples: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for row in rows:
        expected_trigger = str(row.get("expected_trigger") or "")
        predicted_trigger = str(row.get("predicted_trigger") or "")
        predicted_decision = str(row.get("predicted_decision") or "")
        if not expected_trigger or not predicted_trigger:
            continue
        if predicted_decision != "trigger":
            continue
        if expected_trigger == predicted_trigger:
            continue
        key = (expected_trigger, predicted_trigger)
        counter[key] += 1
        query = str(row.get("query") or "").strip()
        if query and len(examples[key]) < 3:
            examples[key].append(query)

    out: List[Dict[str, Any]] = []
    for (exp, pred), count in counter.most_common(max(1, int(top_n))):
        out.append(
            {
                "expected_trigger": exp,
                "predicted_trigger": pred,
                "count": int(count),
                "pair": f"{exp}->{pred}",
                "examples": list(examples.get((exp, pred), [])),
            }
        )
    return out


def summarize_by_trigger(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "expected_total": 0,
            "predicted_total": 0,
            "correct_trigger": 0,
            "missed": 0,
            "wrong_predicted": 0,
            "top_confused_with": {},
        }
    )
    confusion: Dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        expected_trigger = str(row.get("expected_trigger") or "")
        predicted_trigger = str(row.get("predicted_trigger") or "")
        expected_decision = str(row.get("expected_decision") or "")
        predicted_decision = str(row.get("predicted_decision") or "")

        if expected_decision == "trigger" and expected_trigger:
            stats[expected_trigger]["expected_total"] += 1
            if predicted_decision == "trigger" and predicted_trigger == expected_trigger:
                stats[expected_trigger]["correct_trigger"] += 1
            elif predicted_decision != "trigger":
                stats[expected_trigger]["missed"] += 1
            else:
                stats[expected_trigger]["wrong_predicted"] += 1
                if predicted_trigger:
                    confusion[expected_trigger][predicted_trigger] += 1

        if predicted_decision == "trigger" and predicted_trigger:
            stats[predicted_trigger]["predicted_total"] += 1

    out: Dict[str, Dict[str, Any]] = {}
    for trigger_id, item in stats.items():
        exp_total = int(item["expected_total"])
        correct = int(item["correct_trigger"])
        recall = float(correct / max(1, exp_total))
        top_confused = dict(confusion.get(trigger_id, Counter()).most_common(3))
        out[trigger_id] = {
            **item,
            "trigger_recall": round(recall, 4),
            "top_confused_with": top_confused,
        }
    return out


def _compact_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "query": row.get("query"),
        "expected_decision": row.get("expected_decision"),
        "expected_trigger": row.get("expected_trigger"),
        "predicted_decision": row.get("predicted_decision"),
        "predicted_trigger": row.get("predicted_trigger"),
    }
